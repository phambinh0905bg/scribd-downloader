import os
import shutil
import time
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional
from app.config import settings

logger = logging.getLogger("cleanup")

TEMP_EXTENSIONS = {".part", ".ytdl", ".tmp", ".temp", ".crdownload"}

def get_dir_size(path: Path) -> int:
    """Calculate total size of directory in bytes."""
    total = 0
    try:
        if path.is_file():
            return path.stat().st_size
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except Exception:
        pass
    return total

def delete_task_files(task_id: str) -> bool:
    """Explicitly delete all files and directory associated with a task."""
    if not task_id or "/" in task_id or "\\" in task_id or ".." in task_id:
        return False
        
    task_dir = settings.DOWNLOADS_DIR / task_id
    deleted = False
    
    try:
        if task_dir.exists():
            shutil.rmtree(task_dir, ignore_errors=True)
            deleted = True
            logger.info(f"🗑️ Đã xóa tệp và thư mục tác vụ {task_id} theo yêu cầu người dùng.")
    except Exception as e:
        logger.warning(f"Lỗi khi xóa thư mục {task_dir}: {e}")
        
    # Also clean up memory tasks across services
    try:
        from app.downloader import downloader_service
        if task_id in downloader_service.tasks:
            del downloader_service.tasks[task_id]
    except Exception:
        pass

    try:
        from app.youtube import youtube_service
        if task_id in youtube_service.tasks:
            del youtube_service.tasks[task_id]
    except Exception:
        pass

    try:
        from app.facebook import facebook_service
        if task_id in facebook_service.tasks:
            del facebook_service.tasks[task_id]
    except Exception:
        pass

    try:
        from app.direct_downloader import direct_downloader_service
        if task_id in direct_downloader_service.tasks:
            del direct_downloader_service.tasks[task_id]
    except Exception:
        pass
        
    return deleted

def cleanup_expired_and_abandoned_files(
    max_age_minutes: int = settings.CLEANUP_MINUTES,
    abandoned_max_minutes: int = 15
) -> Dict[str, int]:
    """
    Smart Multi-tier Cleaner:
    1. Deletes abandoned/incomplete/temporary files and failed tasks older than 15 minutes.
    2. Deletes completed tasks older than max_age_minutes (5 hours).
    3. Purges intermediate temp folders like temp_images.
    """
    downloads_dir = settings.DOWNLOADS_DIR
    if not downloads_dir.exists():
        return {"deleted_folders": 0, "deleted_files": 0, "freed_bytes": 0}

    now = time.time()
    max_age_seconds = max_age_minutes * 60
    abandoned_max_seconds = abandoned_max_minutes * 60
    
    deleted_folders = 0
    deleted_files = 0
    freed_bytes = 0

    try:
        for item in downloads_dir.iterdir():
            if item.name in [".gitkeep"]:
                continue
                
            if item.name == "temp" and item.is_dir():
                # Clean up expired temp files inside temp folder without deleting the directory itself
                try:
                    for sub in item.iterdir():
                        try:
                            sub_mtime = sub.stat().st_mtime
                            if (now - sub_mtime) > abandoned_max_seconds:
                                sub_size = get_dir_size(sub)
                                if sub.is_dir():
                                    shutil.rmtree(sub, ignore_errors=True)
                                else:
                                    sub.unlink(missing_ok=True)
                                freed_bytes += sub_size
                        except Exception:
                            pass
                except Exception:
                    pass
                continue
                
            try:
                mtime = item.stat().st_mtime

                age_seconds = now - mtime
                item_size = get_dir_size(item)
                
                is_abandoned = False
                
                if item.is_dir():
                    # Check if directory has temp/partial files or temp_images
                    has_temp_images = (item / "temp_images").exists()
                    has_part_files = any(f.suffix.lower() in TEMP_EXTENSIONS for f in item.rglob("*") if f.is_file())
                    files_in_dir = [f for f in item.iterdir() if f.is_file() and f.name != ".gitkeep"]
                    
                    # If older than 15 mins and only contains incomplete files or temp_images
                    if age_seconds > abandoned_max_seconds:
                        if has_temp_images or has_part_files or len(files_in_dir) == 0:
                            is_abandoned = True
                            
                    # Clean up inner temp_images if left over
                    if has_temp_images and age_seconds > 300:
                        shutil.rmtree(item / "temp_images", ignore_errors=True)
                        
                    # Standard expiration for all tasks
                    if age_seconds > max_age_seconds or is_abandoned:
                        shutil.rmtree(item, ignore_errors=True)
                        deleted_folders += 1
                        freed_bytes += item_size
                        reason = "bị người dùng bỏ dở / lỗi tạm" if is_abandoned else "đã hết hạn lưu trữ (5h)"
                        logger.info(f"🗑️ Dọn dẹp thư mục {item.name} ({reason}, dung lượng: {round(item_size/(1024*1024), 2)} MB)")
                        
                else:
                    # Single loose file
                    if age_seconds > max_age_seconds or (item.suffix.lower() in TEMP_EXTENSIONS and age_seconds > abandoned_max_seconds):
                        item.unlink(missing_ok=True)
                        deleted_files += 1
                        freed_bytes += item_size
                        logger.info(f"🗑️ Dọn dẹp tệp tin {item.name} (dung lượng: {round(item_size/(1024*1024), 2)} MB)")
                        
            except Exception as e:
                logger.warning(f"Lỗi kiểm tra/xóa phần tử {item}: {e}")

    except Exception as e:
        logger.error(f"Lỗi trong quá trình quét dọn dẹp: {e}")

    return {
        "deleted_folders": deleted_folders,
        "deleted_files": deleted_files,
        "freed_bytes": freed_bytes,
        "freed_mb": round(freed_bytes / (1024 * 1024), 2)
    }

async def start_cleanup_scheduler():
    """Background async loop to run cleanup periodically."""
    logger.info(f"Auto-cleanup background worker started. TTL={settings.CLEANUP_MINUTES}m (Temp/Abandoned TTL=15m), Interval={settings.CLEANUP_INTERVAL_SECONDS}s")
    while True:
        try:
            cleanup_expired_and_abandoned_files(settings.CLEANUP_MINUTES, abandoned_max_minutes=15)
        except Exception as e:
            logger.error(f"Exception in cleanup loop: {e}")
        await asyncio.sleep(settings.CLEANUP_INTERVAL_SECONDS)

def get_storage_stats() -> Dict:
    """Get current storage usage statistics in downloads folder."""
    downloads_dir = settings.DOWNLOADS_DIR
    total_files = 0
    total_size = 0
    items = []
    now = time.time()

    if downloads_dir.exists():
        for item in downloads_dir.iterdir():
            if item.name == ".gitkeep":
                continue
            if item.is_dir() or item.is_file():
                size = get_dir_size(item)
                mtime = item.stat().st_mtime
                age_minutes = round((now - mtime) / 60, 1)
                remaining_minutes = max(0.0, round(settings.CLEANUP_MINUTES - age_minutes, 1))
                
                total_files += 1
                total_size += size
                items.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size_bytes": size,
                    "size_mb": round(size / (1024 * 1024), 2),
                    "age_minutes": age_minutes,
                    "remaining_minutes": remaining_minutes
                })

    return {
        "total_items": total_files,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "cleanup_ttl_minutes": settings.CLEANUP_MINUTES,
        "items": items
    }
