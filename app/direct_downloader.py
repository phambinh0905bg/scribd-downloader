import os
import re
import time
import shutil
import socket
import asyncio
import logging
import datetime
import mimetypes
import ipaddress
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Any

import requests
from app.config import settings

logger = logging.getLogger("direct_downloader")

def validate_safe_url(url: str) -> None:
    """
    Kiểm tra URL hợp lệ và chống tấn công Server-Side Request Forgery (SSRF).
    Chặn triệt để các kết nối tới IP nội bộ mạng LAN gia đình, localhost, hoặc dải mạng riêng.
    """
    url_clean = url.strip()
    parsed = urllib.parse.urlparse(url_clean)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Chỉ hỗ trợ tải qua giao thức HTTP hoặc HTTPS.")
    
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Đường dẫn tệp tin không hợp lệ.")
        
    # Chặn các hostname nội bộ phổ biến
    lower_host = hostname.lower()
    if lower_host in ("localhost", "127.0.0.1", "0.0.0.0", "broadcasthost", "local", "router.local"):
        raise ValueError("Đường dẫn mạng nội bộ (localhost) đã bị chặn vì lý do bảo mật.")

    try:
        # Phân giải hostname ra IP
        addr_infos = socket.getaddrinfo(hostname, None)
        for family, _, _, _, sockaddr in addr_infos:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                logger.warning(f"Chặn truy cập SSRF tới IP nội bộ: {ip_str} ({hostname})")
                raise ValueError(f"Đường dẫn thuộc dải IP nội bộ/riêng tư ({ip_str}), đã bị chặn để bảo vệ an toàn mạng LAN.")
    except socket.gaierror:
        raise ValueError(f"Không thể phân giải tên miền: {hostname}")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Encoding": "identity",
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
}

def format_bytes_str(num_bytes: int) -> str:
    if not num_bytes or num_bytes <= 0:
        return "Không xác định (Dung lượng động)"
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{round(num_bytes / 1024, 2)} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{round(num_bytes / (1024 * 1024), 2)} MB"
    else:
        return f"{round(num_bytes / (1024 * 1024 * 1024), 2)} GB"


class DirectDownloadTask:
    def __init__(self, task_id: str, url: str, custom_filename: Optional[str] = None):
        self.task_id = task_id
        self.raw_url = url.strip()
        self.custom_filename = custom_filename.strip() if custom_filename else None
        
        self.title: str = "Đang kết nối tới máy chủ tệp tin..."
        self.clean_filename: str = f"file_{task_id}"
        self.content_type: str = "application/octet-stream"
        
        self.status: str = "queued"  # queued, connecting, downloading, compiling, completed, failed
        self.stage_message: str = "Đang trong hàng đợi tải..."
        self.percentage: int = 0
        self.speed: str = ""
        self.eta: str = ""
        self.downloaded_bytes: int = 0
        self.total_bytes: int = 0
        
        self.file_path: Optional[Path] = None
        self.file_size_bytes: int = 0
        self.file_size_mb: float = 0.0
        self.error_message: Optional[str] = None
        self.created_at: float = time.time()
        self.logs: List[Dict[str, str]] = []
        
        # Ensure task directory exists
        self.task_dir = settings.DOWNLOADS_DIR / self.task_id
        self.task_dir.mkdir(parents=True, exist_ok=True)
        
        self.add_log("Khởi tạo tác vụ tải tệp tin trực tiếp từ Remote URL...")

    def add_log(self, message: str, level: str = "info"):
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = {"time": now_str, "level": level, "message": message}
        self.logs.append(log_entry)
        if len(self.logs) > 400:
            self.logs = self.logs[-400:]
            
        if level == "error":
            logger.error(f"[{self.task_id}] {message}")
        elif level == "warning":
            logger.warning(f"[{self.task_id}] {message}")
        else:
            logger.info(f"[{self.task_id}] {message}")

    def update_progress(self, status: str, stage_message: str, percentage: int):
        self.status = status
        self.stage_message = stage_message
        self.percentage = max(self.percentage, max(0, min(100, percentage)))

    def to_dict(self) -> Dict[str, Any]:
        time_left = max(0, int((self.created_at + (settings.CLEANUP_MINUTES * 60)) - time.time()))
        return {
            "task_id": self.task_id,
            "type": "direct",
            "url": self.raw_url,
            "title": self.title,
            "filename": self.clean_filename,
            "content_type": self.content_type,
            "status": self.status,
            "stage_message": self.stage_message,
            "percentage": self.percentage,
            "speed": self.speed,
            "eta": self.eta,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "file_size_bytes": self.file_size_bytes,
            "file_size_mb": self.file_size_mb,
            "download_url": f"/api/file/{self.task_id}" if self.status == "completed" else None,
            "expires_in_seconds": time_left,
            "expires_in_minutes": round(time_left / 60, 1),
            "expires_in_hours": round(time_left / 3600, 1),
            "error_message": self.error_message,
            "logs": self.logs
        }


class DirectDownloaderService:
    def __init__(self):
        self.tasks: Dict[str, DirectDownloadTask] = {}

    def get_task(self, task_id: str) -> Optional[DirectDownloadTask]:
        return self.tasks.get(task_id)

    def sanitize_filename(self, filename: str) -> str:
        clean = urllib.parse.unquote(filename)
        clean = re.sub(r'[\\/*?:"<>|]', "_", clean)
        clean = re.sub(r'\s+', " ", clean).strip()
        return clean[:150] if clean else "downloaded_file"

    def extract_filename_and_size(self, url: str, headers: Dict[str, str], final_url: Optional[str] = None) -> tuple[str, int, str]:
        """Robust parser for filename, total bytes, and MIME content-type from headers and URL"""
        final_url = final_url or url
        parsed = urllib.parse.urlparse(final_url)
        headers_lower = {k.lower(): v for k, v in headers.items()}
        
        # 1. Total Bytes Extraction
        total_bytes = 0
        cr = headers_lower.get("content-range", "")
        if cr:
            m = re.search(r'/(\d+)', cr)
            if m:
                try:
                    total_bytes = int(m.group(1))
                except ValueError:
                    pass
                    
        if total_bytes == 0:
            cl = headers_lower.get("content-length", "")
            if cl and cl.isdigit():
                total_bytes = int(cl)
                
        # 2. Content Type
        content_type = headers_lower.get("content-type", "application/octet-stream").split(";")[0].strip().lower()
        
        # 3. Filename Extraction
        filename = None
        cd = headers_lower.get("content-disposition", "")
        if cd:
            # Check UTF-8 formatted filename
            m = re.search(r"filename\*=UTF-8''([^;\r\n]+)", cd, re.IGNORECASE)
            if not m:
                m = re.search(r'filename="([^"]+)"', cd, re.IGNORECASE)
            if not m:
                m = re.search(r'filename=([^;\r\n]+)', cd, re.IGNORECASE)
            if m:
                extracted = m.group(1).strip("\"' ")
                filename = self.sanitize_filename(extracted)
                
        if not filename:
            # Check Query parameters
            qs = urllib.parse.parse_qs(parsed.query)
            for param in ["filename", "file", "name", "title", "f", "download", "doc"]:
                if param in qs and qs[param][0]:
                    cand = qs[param][0].strip()
                    if cand:
                        filename = self.sanitize_filename(cand)
                        break
                        
        if not filename:
            # Check URL Path
            path_name = Path(parsed.path).name
            if path_name and "." in path_name:
                filename = self.sanitize_filename(path_name)
                
        if not filename:
            ext = mimetypes.guess_extension(content_type) or ".bin"
            filename = f"downloaded_file{ext}"
        elif "." not in filename:
            ext = mimetypes.guess_extension(content_type)
            if ext:
                filename = f"{filename}{ext}"
                
        return filename, total_bytes, content_type

    def extract_info(self, url: str) -> Dict[str, Any]:
        """Inspect Remote URL metadata with multi-tier discovery (HEAD -> Range GET -> Stream GET)"""
        session = requests.Session()
        session.headers.update(DEFAULT_HEADERS)
        
        # Anti-SSRF check
        validate_safe_url(url)
        
        final_url = url
        headers: Dict[str, str] = {}
        
        try:
            # Tier 1: Try Range GET with 1 byte (Gets true Content-Range from almost all CDNs/GitHub/Cloudflare)
            try:
                res_range = session.get(url, headers={**DEFAULT_HEADERS, "Range": "bytes=0-0"}, stream=True, allow_redirects=True, timeout=8)
                if res_range.status_code in [200, 206]:
                    final_url = res_range.url
                    headers = dict(res_range.headers)
            except Exception:
                pass
                
            # Tier 2: Try HEAD if Range GET didn't get total size
            if not headers.get("content-range") and not headers.get("content-length"):
                try:
                    res_head = session.head(url, allow_redirects=True, timeout=8)
                    if res_head.status_code < 400:
                        final_url = res_head.url
                        headers.update(dict(res_head.headers))
                except Exception:
                    pass
                    
            # Tier 3: Streaming GET fallback
            if not headers.get("content-range") and not headers.get("content-length"):
                try:
                    res_stream = session.get(url, stream=True, allow_redirects=True, timeout=8)
                    if res_stream.status_code < 400:
                        final_url = res_stream.url
                        headers.update(dict(res_stream.headers))
                except Exception:
                    pass

            filename, total_bytes, content_type = self.extract_filename_and_size(url, headers, final_url)
            
            size_mb = round(total_bytes / (1024 * 1024), 2) if total_bytes > 0 else 0
            size_str = format_bytes_str(total_bytes)
            
            return {
                "filename": filename,
                "file_size_bytes": total_bytes,
                "file_size_mb": size_mb,
                "file_size_str": size_str,
                "content_type": content_type,
                "url": final_url
            }
        except Exception as e:
            parsed = urllib.parse.urlparse(url)
            fallback_name = Path(parsed.path).name or "remote_file.bin"
            return {
                "filename": self.sanitize_filename(fallback_name),
                "file_size_bytes": 0,
                "file_size_mb": 0,
                "file_size_str": "Không xác định (Dung lượng động)",
                "content_type": "application/octet-stream",
                "url": url
            }

    async def start_download_task(self, task: DirectDownloadTask):
        self.tasks[task.task_id] = task
        asyncio.create_task(self._process_download(task))

    async def _process_download(self, task: DirectDownloadTask):
        task.update_progress("connecting", "Đang kết nối tới máy chủ tệp tin từ xa...", 0)
        
        try:
            validate_safe_url(task.raw_url)
        except Exception as e:
            task.fail_task(f"Lỗi bảo mật: {e}")
            return

        def run_stream_download():
            session = requests.Session()
            session.headers.update(DEFAULT_HEADERS)
            
            task.add_log(f"Đang gửi yêu cầu stream tới: {task.raw_url[:100]}...")
            
            with session.get(task.raw_url, stream=True, allow_redirects=True, timeout=30) as r:
                r.raise_for_status()
                
                headers = dict(r.headers)
                filename, total_bytes, content_type = self.extract_filename_and_size(task.raw_url, headers, r.url)
                
                task.total_bytes = total_bytes
                task.content_type = content_type
                
                final_name = task.custom_filename or filename
                task.clean_filename = self.sanitize_filename(final_name)
                task.title = task.clean_filename
                
                total_mb_str = format_bytes_str(total_bytes)
                task.add_log(f"Tên tệp tin: \"{task.clean_filename}\" | Kích thước: {total_mb_str}")
                task.add_log(f"Loại dữ liệu (MIME): {task.content_type}")
                
                dest_path = task.task_dir / task.clean_filename
                
                downloaded = 0
                start_time = time.time()
                last_update = time.time()
                last_downloaded = 0
                
                chunk_size = 512 * 1024  # 512KB chunks for smooth progress updates
                
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        task.downloaded_bytes = downloaded
                        
                        now = time.time()
                        if now - last_update >= 0.25:
                            duration = now - start_time
                            interval_duration = now - last_update
                            interval_bytes = downloaded - last_downloaded
                            
                            speed = interval_bytes / interval_duration if interval_duration > 0 else 0
                            speed_mb = speed / (1024 * 1024)
                            task.speed = f"{round(speed_mb, 1)} MB/s"
                            
                            cur_mb = round(downloaded / (1024 * 1024), 2)
                            
                            if total_bytes > 0:
                                # Strict calculation based directly on downloaded bytes vs total bytes
                                pct = min(99, int((downloaded / total_bytes) * 100))
                                remaining_bytes = max(0, total_bytes - downloaded)
                                eta_s = int(remaining_bytes / speed) if speed > 0 else 0
                                task.eta = f"ETA: {eta_s}s"
                                
                                tot_mb = round(total_bytes / (1024 * 1024), 2)
                                msg = f"Đang tải: {cur_mb} MB / {tot_mb} MB ({task.speed}) - {task.eta}"
                            else:
                                pct = min(95, max(1, int(duration * 2)))
                                msg = f"Đang tải: {cur_mb} MB ({task.speed})"
                                
                            task.update_progress("downloading", msg, pct)
                            last_update = now
                            last_downloaded = downloaded
                            
                return dest_path

        try:
            task.update_progress("downloading", "Bắt đầu tải luồng tệp tin...", 1)
            final_path = await asyncio.to_thread(run_stream_download)
            
            task.file_path = final_path
            task.file_size_bytes = final_path.stat().st_size
            task.file_size_mb = round(task.file_size_bytes / (1024 * 1024), 2)
            
            size_display = format_bytes_str(task.file_size_bytes)
            task.add_log(f"🎉 Tải tệp thành công: {task.clean_filename} (Dung lượng: {size_display})")
            task.add_log(f"⏰ File đã được lưu trữ an toàn và sẽ tự động xóa sau {settings.CLEANUP_MINUTES} phút (5 giờ).")
            task.update_progress("completed", f"Hoàn tất! Tệp {task.clean_filename} ({size_display}) đã sẵn sàng tải về.", 100)
            
        except Exception as e:
            task.error_message = f"Lỗi tải tệp tin từ xa: {str(e)}"
            task.add_log(f"Lỗi: {str(e)}", level="error")
            task.update_progress("failed", task.error_message, 0)

direct_downloader_service = DirectDownloaderService()
