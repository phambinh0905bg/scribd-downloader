import os
import re
import time
import shutil
import asyncio
import logging
import datetime
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Any

import requests
from app.config import settings

logger = logging.getLogger("direct_downloader")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
}

class DirectDownloadTask:
    def __init__(self, task_id: str, url: str, custom_filename: Optional[str] = None):
        self.task_id = task_id
        self.raw_url = url.strip()
        self.custom_filename = custom_filename.strip() if custom_filename else None
        
        self.title: str = "Đang kết nối tới máy chủ tệp tin..."
        self.clean_filename: str = f"file_{task_id}"
        self.content_type: str = "application/octet-stream"
        
        self.status: str = "queued"  # queued, connecting, downloading, completed, failed
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
        
        self.add_log(f"Khởi tạo tác vụ tải tệp tin trực tiếp từ Remote URL...")

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

    def extract_filename_from_headers_or_url(self, url: str, headers: Dict[str, str]) -> str:
        # 1. Check Content-Disposition header
        cd = headers.get("content-disposition", "")
        if cd:
            match = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';\r\n]+)["\']?', cd, re.IGNORECASE)
            if match:
                return self.sanitize_filename(match.group(1))
                
        # 2. Check URL path
        parsed = urllib.parse.urlparse(url)
        path_name = Path(parsed.path).name
        if path_name and "." in path_name:
            return self.sanitize_filename(path_name)
            
        return "remote_file.bin"

    def extract_info(self, url: str) -> Dict[str, Any]:
        """Inspect Remote URL metadata: filename, content length, content type"""
        session = requests.Session()
        session.headers.update(DEFAULT_HEADERS)
        
        try:
            # First try HEAD request
            res = session.head(url, allow_redirects=True, timeout=12)
            if res.status_code >= 400 or not res.headers.get("content-length"):
                # Fallback to streaming GET request (just headers)
                res = session.get(url, stream=True, allow_redirects=True, timeout=12)
                
            final_url = res.url
            headers = res.headers
            
            content_length = int(headers.get("content-length", 0))
            content_type = headers.get("content-type", "application/octet-stream").split(";")[0].strip()
            filename = self.extract_filename_from_headers_or_url(final_url, dict(headers))
            
            size_mb = round(content_length / (1024 * 1024), 2) if content_length > 0 else 0
            size_str = f"{size_mb} MB" if size_mb > 0 else "Không xác định (Dung lượng động)"
            
            return {
                "filename": filename,
                "file_size_bytes": content_length,
                "file_size_mb": size_mb,
                "file_size_str": size_str,
                "content_type": content_type,
                "url": final_url
            }
        except Exception as e:
            # Fallback filename from url
            parsed = urllib.parse.urlparse(url)
            fallback_name = Path(parsed.path).name or "remote_file.bin"
            return {
                "filename": fallback_name,
                "file_size_bytes": 0,
                "file_size_mb": 0,
                "file_size_str": "Không xác định",
                "content_type": "application/octet-stream",
                "url": url
            }

    async def start_download_task(self, task: DirectDownloadTask):
        self.tasks[task.task_id] = task
        asyncio.create_task(self._process_download(task))

    async def _process_download(self, task: DirectDownloadTask):
        task.update_progress("connecting", "Đang kết nối tới máy chủ tệp tin từ xa...", 0)
        
        def run_stream_download():
            session = requests.Session()
            session.headers.update(DEFAULT_HEADERS)
            
            task.add_log(f"Đang gửi yêu cầu stream tới: {task.raw_url[:100]}...")
            
            with session.get(task.raw_url, stream=True, allow_redirects=True, timeout=30) as r:
                r.raise_for_status()
                
                headers = dict(r.headers)
                total_bytes = int(headers.get("content-length", 0))
                task.total_bytes = total_bytes
                task.content_type = headers.get("content-type", "application/octet-stream").split(";")[0].strip()
                
                detected_name = self.extract_filename_from_headers_or_url(r.url, headers)
                final_name = task.custom_filename or detected_name
                task.clean_filename = self.sanitize_filename(final_name)
                task.title = task.clean_filename
                
                total_mb_str = f"{round(total_bytes / (1024*1024), 2)} MB" if total_bytes > 0 else "Không giới hạn"
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
                        if now - last_update >= 0.3:
                            duration = now - start_time
                            interval_duration = now - last_update
                            interval_bytes = downloaded - last_downloaded
                            
                            speed = interval_bytes / interval_duration if interval_duration > 0 else 0
                            speed_mb = speed / (1024 * 1024)
                            task.speed = f"{round(speed_mb, 1)} MB/s"
                            
                            cur_mb = round(downloaded / (1024 * 1024), 2)
                            
                            if total_bytes > 0:
                                # Direct calculation based purely on downloaded bytes vs total file size
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
            
            task.add_log(f"🎉 Tải tệp thành công: {task.clean_filename} (Dung lượng: {task.file_size_mb} MB)")
            task.add_log(f"⏰ File đã được lưu trữ an toàn và sẽ tự động xóa sau {settings.CLEANUP_MINUTES} phút (5 giờ).")
            task.update_progress("completed", f"Hoàn tất! Tệp {task.clean_filename} ({task.file_size_mb} MB) đã sẵn sàng tải về.", 100)
            
        except Exception as e:
            task.error_message = f"Lỗi tải tệp tin từ xa: {str(e)}"
            task.add_log(f"Lỗi: {str(e)}", level="error")
            task.update_progress("failed", task.error_message, 0)


direct_downloader_service = DirectDownloaderService()

