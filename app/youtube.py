import os
import re
import time
import shutil
import asyncio
import logging
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from app.config import settings

logger = logging.getLogger("youtube")

class YouTubeTask:
    def __init__(self, task_id: str, url: str, format_type: str = "video", quality: str = "best"):
        self.task_id = task_id
        self.raw_url = url.strip()
        self.format_type = format_type.lower()  # "video" or "audio"
        self.quality = quality                  # "best", "2160p", "1440p", "1080p", "720p", "480p", "360p", "320k", "192k", "128k", "m4a"
        
        self.title: str = "Đang phân tích video YouTube..."
        self.uploader: str = ""
        self.duration_str: str = ""
        self.thumbnail: str = ""
        self.clean_filename: str = f"youtube_{task_id}.mp4"
        
        self.status: str = "queued"  # queued, connecting, extracting, downloading, compiling, completed, failed
        self.stage_message: str = "Đang khởi tạo tác vụ..."
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
        
        self.add_log("Khởi tạo tác vụ tải video/audio từ YouTube...")

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
            "type": "youtube",
            "url": self.raw_url,
            "title": self.title,
            "uploader": self.uploader,
            "duration": self.duration_str,
            "thumbnail": self.thumbnail,
            "format_type": self.format_type,
            "quality": self.quality,
            "filename": self.clean_filename,
            "status": self.status,
            "stage_message": self.stage_message,
            "percentage": self.percentage,
            "speed": self.speed,
            "eta": self.eta,
            "file_size_bytes": self.file_size_bytes,
            "file_size_mb": self.file_size_mb,
            "download_url": f"/api/file/{self.task_id}" if self.status == "completed" else None,
            "expires_in_seconds": time_left,
            "expires_in_minutes": round(time_left / 60, 1),
            "error_message": self.error_message,
            "logs": self.logs
        }


class YtDlpCustomLogger:
    def __init__(self, task: YouTubeTask):
        self.task = task
        
    def debug(self, msg: str):
        msg = msg.strip()
        if not msg:
            return
        if "[ffmpeg]" in msg or "[Merger]" in msg or "[ExtractAudio]" in msg or "Destination" in msg or "Converting" in msg or "Merging" in msg:
            clean_msg = re.sub(r'\x1b\[[0-9;]*m', '', msg)
            self.task.add_log(f"🎬 {clean_msg}")
            if "Destination" in clean_msg:
                self.task.update_progress("compiling", f"FFmpeg đang ghi file: {Path(clean_msg.split(':', 1)[-1].strip()).name}...", 94)
            elif "Deleting original" in clean_msg:
                self.task.add_log("🧹 FFmpeg đang dọn dẹp các luồng tạm...")
                
    def info(self, msg: str):
        msg = msg.strip()
        if not msg:
            return
        clean_msg = re.sub(r'\x1b\[[0-9;]*m', '', msg)
        if "[ffmpeg]" in clean_msg or "[Merger]" in clean_msg or "[ExtractAudio]" in clean_msg:
            self.task.add_log(f"🎬 {clean_msg}")
            
    def warning(self, msg: str):
        self.task.add_log(f"⚠️ {msg.strip()}", level="warning")
        
    def error(self, msg: str):
        self.task.add_log(f"❌ {msg.strip()}", level="error")


class YouTubeDownloaderService:
    def __init__(self):
        self.tasks: Dict[str, YouTubeTask] = {}
        self.active_downloads = 0

    def get_task(self, task_id: str) -> Optional[YouTubeTask]:
        return self.tasks.get(task_id)

    def sanitize_filename(self, filename: str) -> str:
        clean = re.sub(r'[\\/*?:"<>|]', "", filename)
        clean = re.sub(r'\s+', " ", clean).strip()
        return clean[:120] if clean else "youtube_media"

    def format_duration(self, seconds: Any) -> str:
        if not seconds:
            return ""
        try:
            total_seconds = int(float(seconds))
        except (ValueError, TypeError):
            return ""
        m, s = divmod(total_seconds, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"


    def extract_info(self, url: str) -> Dict[str, Any]:
        """Fetch quick video metadata and available qualities without downloading"""
        if not yt_dlp:
            raise RuntimeError("Thư viện yt-dlp chưa được cài đặt.")
            
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            title = info.get("title", "Video YouTube")
            uploader = info.get("uploader") or info.get("channel") or ""
            duration = self.format_duration(info.get("duration"))
            thumbnail = info.get("thumbnail") or ""
            description = (info.get("description") or "")[:200]
            
            # Extract available heights & build dynamic quality list
            formats = info.get("formats", [])
            seen_heights = set()
            
            height_labels = {
                4320: "8K Ultra HD (4320p)",
                2160: "4K Ultra HD (2160p)",
                1440: "2K Quad HD (1440p)",
                1080: "Full HD (1080p)",
                720: "HD (720p)",
                480: "SD (480p)",
                360: "360p (Tiết kiệm dữ liệu)",
                240: "240p (Nhẹ)",
                144: "144p (Rất nhẹ)"
            }
            
            detected_qualities = []
            
            for f in formats:
                h = f.get("height")
                vcodec = f.get("vcodec", "")
                fps = f.get("fps")
                if h and vcodec != "none" and h not in seen_heights:
                    seen_heights.add(h)
                    base_lbl = height_labels.get(h, f"{h}p")
                    if fps and fps >= 50:
                        base_lbl += f" {int(fps)}fps"
                    detected_qualities.append({
                        "id": f"{h}p",
                        "label": base_lbl,
                        "height": h,
                        "fps": fps
                    })
                    
            # Sort qualities by resolution descending
            sorted_video_qualities = sorted(detected_qualities, key=lambda x: x["height"], reverse=True)
            
            # Always have "best" option at the top
            video_options = [
                {
                    "id": "best",
                    "label": "⭐ Chất lượng cao nhất (Tự động chọn)",
                    "height": 9999
                }
            ] + sorted_video_qualities
            
            # Audio Qualities
            audio_options = [
                {"id": "320k", "label": "MP3 - 320 kbps (Chất lượng phòng thu)", "note": "Siêu sắc nét"},
                {"id": "192k", "label": "MP3 - 192 kbps (Tiêu chuẩn cao)", "note": "Khuyến nghị"},
                {"id": "128k", "label": "MP3 - 128 kbps (Phổ thông / Tiết kiệm dung lượng)", "note": "Nhẹ"},
                {"id": "m4a", "label": "M4A / AAC (Bản gốc không nén lại)", "note": "Bản gốc"}
            ]
            
            return {
                "title": title,
                "uploader": uploader,
                "duration": duration,
                "thumbnail": thumbnail,
                "description": description,
                "video_qualities": video_options,
                "audio_qualities": audio_options,
                "url": url
            }

    async def start_download_task(self, task: YouTubeTask):
        self.tasks[task.task_id] = task
        asyncio.create_task(self._process_download(task))

    async def _process_download(self, task: YouTubeTask):
        task.update_progress("connecting", "Đang kết nối tới máy chủ YouTube...", 10)
        
        current_stream_filename = [None]
        stream_index = [0]
        
        def progress_hook(d):
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                
                speed = d.get("speed")
                eta = d.get("eta")
                
                fn = d.get("filename")
                if fn and fn != current_stream_filename[0]:
                    current_stream_filename[0] = fn
                    stream_index[0] += 1
                
                pct = 15
                if total > 0:
                    ratio = min(1.0, downloaded / total)
                    if task.format_type == "video":
                        if stream_index[0] <= 1:
                            # Stream 1 (Video): 15% -> 70%
                            pct = 15 + int(ratio * 55)
                        else:
                            # Stream 2 (Audio): 70% -> 85%
                            pct = 70 + int(ratio * 15)
                    else:
                        # Audio-only: 15% -> 85%
                        pct = 15 + int(ratio * 70)
                        
                    task.total_bytes = total
                    task.downloaded_bytes = downloaded
                
                speed_str = f"{round(speed / (1024*1024), 1)} MB/s" if speed else ""
                eta_str = f"ETA: {int(eta)}s" if eta else ""
                
                task.speed = speed_str
                task.eta = eta_str
                
                downloaded_mb = round(downloaded / (1024*1024), 1)
                total_mb = round(total / (1024*1024), 1) if total else "?"
                
                msg = f"Đang tải luồng dữ liệu: {downloaded_mb} MB / {total_mb} MB"
                if speed_str:
                    msg += f" ({speed_str})"
                if eta_str:
                    msg += f" - {eta_str}"
                    
                task.update_progress("downloading", msg, pct)
                
            elif d.get("status") == "finished":
                task.update_progress("compiling", "Đang chuyển tiếp tới FFmpeg để xử lý và đóng gói...", 88)
                task.add_log("✅ Nạp xong luồng stream gốc. Bắt đầu chuyển sang FFmpeg xử lý...")


        def postprocessor_hook(d):
            status = d.get("status")
            pp = d.get("postprocessor")
            if status == "started":
                if "ExtractAudio" in str(pp):
                    task.update_progress("compiling", "FFmpeg: Đang trích xuất & chuyển đổi mã âm thanh sang MP3...", 90)
                    task.add_log(f"🎬 FFmpeg: Bắt đầu trích xuất âm thanh chất lượng cao ({task.quality})...")
                elif "Merger" in str(pp):
                    task.update_progress("compiling", "FFmpeg: Đang ghép hợp nhất luồng Video và Audio HD...", 90)
                    task.add_log(f"🎬 FFmpeg: Bắt đầu ghép luồng hình ảnh & âm thanh thành file MP4 hoàn chỉnh...")
                else:
                    task.update_progress("compiling", f"FFmpeg: Đang xử lý hậu kỳ ({pp})...", 90)
                    task.add_log(f"🎬 FFmpeg: Khởi chạy module xử lý {pp}...")
            elif status == "processing":
                task.add_log(f"⏳ FFmpeg: Đang xử lý chuyển đổi dữ liệu...")
            elif status == "finished":
                task.update_progress("compiling", "FFmpeg hoàn tất chuyển đổi! Đang lưu tệp tin thành phẩm...", 97)
                task.add_log(f"✅ FFmpeg: Hoàn tất chuyển mã & ghép luồng ({pp}).")

        def run_ytdlp():
            if not yt_dlp:
                raise RuntimeError("yt-dlp không được cài đặt.")
                
            outtmpl = str(task.task_dir / "%(title)s.%(ext)s")
            custom_logger = YtDlpCustomLogger(task)
            
            ydl_opts: Dict[str, Any] = {
                "outtmpl": outtmpl,
                "progress_hooks": [progress_hook],
                "postprocessor_hooks": [postprocessor_hook],
                "logger": custom_logger,
                "quiet": False,
                "no_warnings": False,
            }
            
            # Format selection
            if task.format_type == "audio":
                task.add_log(f"Chế độ tải: Âm thanh (Audio MP3) - Tùy chọn: {task.quality}")
                quality_map = {
                    "320k": "320",
                    "320": "320",
                    "192k": "192",
                    "192": "192",
                    "128k": "128",
                    "128": "128",
                    "best": "0"
                }
                audio_quality = quality_map.get(task.quality, "192")
                
                if task.quality == "m4a":
                    ydl_opts.update({
                        "format": "bestaudio[ext=m4a]/bestaudio/best",
                    })
                else:
                    ydl_opts.update({
                        "format": "bestaudio/best",
                        "postprocessors": [{
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": audio_quality,
                        }],
                    })
            else:
                # Video format
                height_match = re.search(r'(\d+)', task.quality)
                max_h = int(height_match.group(1)) if height_match else 0
                
                task.add_log(f"Chế độ tải: Video MP4 - Độ phân giải: {task.quality}")
                
                if max_h > 0:
                    ydl_opts.update({
                        "format": f"bestvideo[height<={max_h}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={max_h}]+bestaudio/best[height<={max_h}]/best",
                        "merge_output_format": "mp4",
                    })
                else:
                    ydl_opts.update({
                        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
                        "merge_output_format": "mp4",
                    })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(task.raw_url, download=True)
                return info

        try:
            task.add_log("Đang phân tích định dạng và tìm kiếm máy chủ luồng stream...")
            task.update_progress("extracting", "Đang trích xuất thông tin luồng video/audio...", 15)
            
            info = await asyncio.to_thread(run_ytdlp)
            
            raw_title = info.get("title", f"YouTube_Media_{task.task_id}")
            task.title = raw_title
            task.uploader = info.get("uploader") or info.get("channel") or ""
            task.duration_str = self.format_duration(info.get("duration"))
            task.thumbnail = info.get("thumbnail") or ""
            
            task.add_log(f"Tiêu đề: \"{task.title}\" | Thời lượng: {task.duration_str}")
            
            # Find the downloaded file in task_dir
            downloaded_files = [f for f in task.task_dir.iterdir() if f.is_file()]
            if not downloaded_files:
                raise RuntimeError("Không tìm thấy tệp đầu ra sau khi tải.")
                
            # Pick largest file or matching ext
            final_file = max(downloaded_files, key=lambda f: f.stat().st_size)
            
            safe_name = self.sanitize_filename(task.title)
            ext = final_file.suffix
            safe_filename = f"{safe_name}{ext}"
            
            final_dest = task.task_dir / safe_filename
            if final_file != final_dest:
                final_file.rename(final_dest)
                
            task.file_path = final_dest
            task.clean_filename = safe_filename
            task.file_size_bytes = final_dest.stat().st_size
            task.file_size_mb = round(task.file_size_bytes / (1024 * 1024), 2)
            
            task.add_log(f"🎉 Tải & Xử lý FFmpeg thành công: {task.clean_filename} (Dung lượng: {task.file_size_mb} MB)")
            task.add_log(f"⏰ File sẽ tự động lưu trữ và xóa sau {settings.CLEANUP_MINUTES} phút.")
            task.update_progress("completed", f"Hoàn tất! Tệp {task.clean_filename} ({task.file_size_mb} MB) đã sẵn sàng.", 100)
            
        except Exception as e:
            task.error_message = f"Lỗi tải YouTube: {str(e)}"
            task.add_log(f"Lỗi: {str(e)}", level="error")
            task.update_progress("failed", task.error_message, 0)

youtube_service = YouTubeDownloaderService()
