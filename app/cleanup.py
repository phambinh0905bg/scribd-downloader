import os
import shutil
import time
import asyncio
import logging
from pathlib import Path
from typing import Dict, List
from app.config import settings

logger = logging.getLogger("cleanup")

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

def cleanup_expired_files(max_age_minutes: int = settings.CLEANUP_MINUTES) -> Dict[str, int]:
    """
    Scan downloads directory and delete files/folders older than max_age_minutes.
    Returns summary of deleted files and freed space.
    """
    downloads_dir = settings.DOWNLOADS_DIR
    if not downloads_dir.exists():
        return {"deleted_folders": 0, "deleted_files": 0, "freed_bytes": 0}

    now = time.time()
    max_age_seconds = max_age_minutes * 60
    deleted_folders = 0
    deleted_files = 0
    freed_bytes = 0

    try:
        for item in downloads_dir.iterdir():
            try:
                # Check modification time
                mtime = item.stat().st_mtime
                age_seconds = now - mtime
                
                if age_seconds > max_age_seconds:
                    item_size = get_dir_size(item)
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                        deleted_folders += 1
                    else:
                        item.unlink(missing_ok=True)
                        deleted_files += 1
                    
                    freed_bytes += item_size
                    logger.info(f"Cleaned up expired download: {item.name} (age: {int(age_seconds/60)}m, freed: {item_size} bytes)")
            except Exception as e:
                logger.warning(f"Error checking/deleting item {item}: {e}")

    except Exception as e:
        logger.error(f"Error during cleanup scan: {e}")

    return {
        "deleted_folders": deleted_folders,
        "deleted_files": deleted_files,
        "freed_bytes": freed_bytes
    }

async def start_cleanup_scheduler():
    """Background async loop to run cleanup periodically."""
    logger.info(f"Auto-cleanup background worker started. TTL={settings.CLEANUP_MINUTES}m, Interval={settings.CLEANUP_INTERVAL_SECONDS}s")
    while True:
        try:
            cleanup_expired_files(settings.CLEANUP_MINUTES)
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

