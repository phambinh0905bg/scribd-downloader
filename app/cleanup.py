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

def is_task_actively_running(task_id: str) -> bool:
    """
    Check if a task is currently actively downloading/rendering in memory.
    Active tasks must NEVER be deleted.
    """
    active_statuses = {"queued", "connecting", "extracting", "rendering", "downloading", "compiling"}
    
    # 1. Check Scribd
    try:
        from app.downloader import downloader_service
        t = downloader_service.get_task(task_id)
        if t and t.status in active_statuses:
            return True
    except Exception:
        pass
        
    # 2. Check YouTube
    try:
        from app.youtube import youtube_service
        t = youtube_service.get_task(task_id)
        if t and t.status in active_statuses:
            return True
    except Exception:
        pass
        
    # 3. Check Facebook
    try:
        from app.facebook import facebook_service
        t = facebook_service.get_task(task_id)
        if t and t.status in active_statuses:
            return True
    except Exception:
        pass
        
    # 4. Check Direct Downloader
    try:
        from app.direct_downloader import direct_downloader_service
        t = direct_downloader_service.get_task(task_id)
        if t and t.status in active_statuses:
            return True
    except Exception:
        pass
        
    return False

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
    Bulletproof Multi-tier Cleaner:
    1. NEVER deletes any task currently downloading/rendering or actively writing bytes to disk.
    2. Completed files are strictly preserved for the FULL 5 HOURS (300 minutes).
    3. ONLY deletes abandoned/failed/cancelled tasks that have been completely inactive (no I/O) for > 15 minutes.
    4. Protects the root 'temp' directory from deletion.
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
                
            # Protect system temp directory - only clean files inside it
            if item.name == "temp" and item.is_dir():
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
                
                # RULE 0: If item has a .pinned marker file, NEVER DELETE IT (Permanently Pinned by user)!
                if item.is_dir() and (item / ".pinned").exists():
                    continue

                # RULE 1: If task is currently active in memory, NEVER touch it!
                if is_task_actively_running(item.name):
                    continue

                if item.is_dir():
                    # RULE 2: Check disk I/O liveness. If any file was written in the last 5 minutes, DO NOT touch!
                    all_files = [f for f in item.rglob("*") if f.is_file()]
                    last_write_time = max([f.stat().st_mtime for f in all_files] + [mtime])
                    if (now - last_write_time) < 300:
                        continue

                    # Check file contents
                    has_part_files = any(f.suffix.lower() in TEMP_EXTENSIONS for f in all_files)
                    has_completed_file = any(f.is_file() and f.suffix.lower() not in TEMP_EXTENSIONS and f.name != ".gitkeep" for f in item.iterdir())
                    
                    # RULE 3: Completed files are guaranteed 5 HOURS retention!
                    if has_completed_file and not has_part_files:
                        if age_seconds > max_age_seconds:
                            shutil.rmtree(item, ignore_errors=True)
                            deleted_folders += 1
                            freed_bytes += item_size
                            logger.info(f"🗑️ Dọn dẹp tệp đã hết hạn lưu trữ 5 giờ: {item.name} (dung lượng: {round(item_size/(1024*1024), 2)} MB)")
                        continue

                    # RULE 4: Clean up inner temp_images if left over after rendering
                    temp_img_dir = item / "temp_images"
                    if temp_img_dir.exists() and (now - last_write_time) > 300:
                        shutil.rmtree(temp_img_dir, ignore_errors=True)
                        
                    # RULE 5: Abandoned/failed tasks (dead I/O > 15 minutes and no completed file)
                    if age_seconds > abandoned_max_seconds and (now - last_write_time) > abandoned_max_seconds:
                        shutil.rmtree(item, ignore_errors=True)
                        deleted_folders += 1
                        freed_bytes += item_size
                        logger.info(f"🗑️ Dọn dẹp tác vụ lỗi/bỏ dở quá 15 phút: {item.name} (dung lượng: {round(item_size/(1024*1024), 2)} MB)")
                        
                else:
                    # Single loose file
                    if age_seconds > max_age_seconds or (item.suffix.lower() in TEMP_EXTENSIONS and age_seconds > abandoned_max_seconds):
                        item.unlink(missing_ok=True)
                        deleted_files += 1
                        freed_bytes += item_size
                        logger.info(f"🗑️ Dọn dẹp tệp tin rời {item.name} (dung lượng: {round(item_size/(1024*1024), 2)} MB)")
                        
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
            if item.name in [".gitkeep", "temp"]:
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
