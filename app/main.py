import os
import uuid
import json
import asyncio
import logging
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.config import settings
from app.downloader import downloader_service, DownloadTask
from app.youtube import youtube_service, YouTubeTask
from app.facebook import facebook_service, FacebookTask
from app.direct_downloader import direct_downloader_service, DirectDownloadTask
from app.cleanup import start_cleanup_scheduler, cleanup_expired_and_abandoned_files, get_storage_stats, delete_task_files

# Route all system and library temporary files to high-capacity storage (disk1)
settings.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
os.environ["TMPDIR"] = str(settings.TEMP_DIR)
os.environ["TEMP"] = str(settings.TEMP_DIR)
os.environ["TMP"] = str(settings.TEMP_DIR)
tempfile.tempdir = str(settings.TEMP_DIR)

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_task = asyncio.create_task(start_cleanup_scheduler())
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} started on port {settings.PORT} | Downloads dir: {settings.DOWNLOADS_DIR}")
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("Application shutdown complete.")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)


# Mount static and template directories
static_dir = Path(__file__).parent / "static"
templates_dir = Path(__file__).parent / "templates"

static_dir.mkdir(parents=True, exist_ok=True)
templates_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))


class ScribdDownloadRequest(BaseModel):
    url: str
    pages: Optional[str] = "all"


class YouTubeInfoRequest(BaseModel):
    url: str


class YouTubeDownloadRequest(BaseModel):
    url: str
    format_type: Optional[str] = "video"  # "video" or "audio"
    quality: Optional[str] = "best"


class FacebookInfoRequest(BaseModel):
    url: str


class FacebookDownloadRequest(BaseModel):
    url: str
    format_type: Optional[str] = "video"  # "video" or "audio"
    quality: Optional[str] = "best"


class DirectInfoRequest(BaseModel):
    url: str


class DirectDownloadRequest(BaseModel):
    url: str
    custom_filename: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.APP_NAME,
            "app_version": settings.APP_VERSION,
            "cleanup_minutes": settings.CLEANUP_MINUTES,
            "cleanup_hours": round(settings.CLEANUP_MINUTES / 60, 1)
        }
    )


# --- SCRIBD ENDPOINTS ---

@app.post("/api/download")
async def start_scribd_download(req: ScribdDownloadRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Vui lòng nhập đường dẫn URL tài liệu Scribd.")
    
    doc_id = downloader_service.extract_doc_id(url)
    if not doc_id:
        raise HTTPException(status_code=400, detail="URL không hợp lệ hoặc không tìm thấy ID tài liệu Scribd.")
    
    task_id = str(uuid.uuid4())[:8]
    task = downloader_service.create_task(task_id, url, req.pages or "all")
    
    asyncio.create_task(downloader_service.run_download_task(task))
    
    return {
        "status": "success",
        "task_id": task_id,
        "doc_id": doc_id,
        "message": "Đã khởi tạo tác vụ tải tài liệu."
    }


# --- YOUTUBE ENDPOINTS ---

@app.post("/api/youtube/info")
async def get_youtube_video_info(req: YouTubeInfoRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Vui lòng nhập URL YouTube.")
    try:
        info = await asyncio.to_thread(youtube_service.extract_info, url)
        return {"status": "success", "data": info}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không thể đọc thông tin video YouTube: {str(e)}")


@app.post("/api/youtube/download")
async def start_youtube_download(req: YouTubeDownloadRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Vui lòng nhập URL YouTube.")
        
    task_id = str(uuid.uuid4())[:8]
    task = YouTubeTask(
        task_id=task_id,
        url=url,
        format_type=req.format_type or "video",
        quality=req.quality or "best"
    )
    
    await youtube_service.start_download_task(task)
    
    return {
        "status": "success",
        "task_id": task_id,
        "message": "Đã khởi tạo tác vụ tải video/audio YouTube."
    }


# --- FACEBOOK ENDPOINTS ---

@app.post("/api/facebook/info")
async def get_facebook_video_info(req: FacebookInfoRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Vui lòng nhập URL Facebook.")
    try:
        info = await asyncio.to_thread(facebook_service.extract_info, url)
        return {"status": "success", "data": info}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không thể đọc thông tin video Facebook: {str(e)}")


@app.post("/api/facebook/download")
async def start_facebook_download(req: FacebookDownloadRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Vui lòng nhập URL Facebook.")
        
    task_id = str(uuid.uuid4())[:8]
    task = FacebookTask(
        task_id=task_id,
        url=url,
        format_type=req.format_type or "video",
        quality=req.quality or "best"
    )
    
    await facebook_service.start_download_task(task)
    
    return {
        "status": "success",
        "task_id": task_id,
        "message": "Đã khởi tạo tác vụ tải video/audio Facebook."
    }


# --- REMOTE DIRECT URL ENDPOINTS ---

@app.post("/api/direct/info")
async def get_direct_file_info(req: DirectInfoRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Vui lòng nhập URL tệp tin.")
    try:
        info = await asyncio.to_thread(direct_downloader_service.extract_info, url)
        return {"status": "success", "data": info}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không thể lấy thông tin tệp: {str(e)}")


@app.post("/api/direct/download")
async def start_direct_file_download(req: DirectDownloadRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Vui lòng nhập URL tệp tin.")
        
    task_id = str(uuid.uuid4())[:8]
    task = DirectDownloadTask(
        task_id=task_id,
        url=url,
        custom_filename=req.custom_filename
    )
    
    await direct_downloader_service.start_download_task(task)
    
    return {
        "status": "success",
        "task_id": task_id,
        "message": "Đã khởi tạo tác vụ tải tệp tin từ xa."
    }


# --- UNIVERSAL STATUS & STREAMING ---

@app.get("/api/status/{task_id}")
async def get_task_status(task_id: str):
    # 1. Check Scribd tasks
    task = downloader_service.get_task(task_id)
    if task:
        return task.to_dict()
        
    # 2. Check YouTube tasks
    yt_task = youtube_service.get_task(task_id)
    if yt_task:
        return yt_task.to_dict()
        
    # 3. Check Facebook tasks
    fb_task = facebook_service.get_task(task_id)
    if fb_task:
        return fb_task.to_dict()
        
    # 4. Check Direct Remote Download tasks
    dir_task = direct_downloader_service.get_task(task_id)
    if dir_task:
        return dir_task.to_dict()
        
    raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ hoặc tác vụ đã hết hạn.")


@app.get("/api/stream/{task_id}")
async def stream_task_progress(task_id: str):
    """Server-Sent Events (SSE) stream for real-time progress updates."""
    task = downloader_service.get_task(task_id)
    yt_task = youtube_service.get_task(task_id)
    fb_task = facebook_service.get_task(task_id)
    dir_task = direct_downloader_service.get_task(task_id)
    
    if not task and not yt_task and not fb_task and not dir_task:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ tải.")

    async def event_generator():
        if task:
            queue = task.subscribe()
            try:
                while True:
                    try:
                        data = await asyncio.wait_for(queue.get(), timeout=15.0)
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                        if data.get("status") in ["completed", "failed"]:
                            await asyncio.sleep(0.5)
                            break
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"
            finally:
                task.unsubscribe(queue)
        else:
            # Polling stream generator for YouTube, Facebook and Direct tasks
            target_task = yt_task or fb_task or dir_task
            last_status = None
            last_pct = -1
            last_log_count = 0
            
            for _ in range(1200):  # max 20 minutes
                if not target_task:
                    break
                data = target_task.to_dict()
                curr_status = data.get("status")
                curr_pct = data.get("percentage")
                curr_log_count = len(data.get("logs", []))
                
                if curr_status != last_status or curr_pct != last_pct or curr_log_count != last_log_count:
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    last_status = curr_status
                    last_pct = curr_pct
                    last_log_count = curr_log_count
                    
                if curr_status in ["completed", "failed"]:
                    await asyncio.sleep(0.5)
                    break
                    
                await asyncio.sleep(0.6)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/file/{task_id}")
async def download_output_file(task_id: str):
    # Check Scribd task
    task = downloader_service.get_task(task_id)
    if task and task.status == "completed" and task.pdf_path and task.pdf_path.exists():
        return FileResponse(
            path=str(task.pdf_path),
            filename=task.clean_filename,
            media_type="application/pdf"
        )
        
    # Check YouTube task
    yt_task = youtube_service.get_task(task_id)
    if yt_task and yt_task.status == "completed" and yt_task.file_path and yt_task.file_path.exists():
        ext = yt_task.file_path.suffix.lower()
        content_type = "video/mp4" if ext == ".mp4" else ("audio/mpeg" if ext == ".mp3" else "application/octet-stream")
        return FileResponse(
            path=str(yt_task.file_path),
            filename=yt_task.clean_filename,
            media_type=content_type
        )
        
    # Check Facebook task
    fb_task = facebook_service.get_task(task_id)
    if fb_task and fb_task.status == "completed" and fb_task.file_path and fb_task.file_path.exists():
        ext = fb_task.file_path.suffix.lower()
        content_type = "video/mp4" if ext == ".mp4" else ("audio/mpeg" if ext == ".mp3" else "application/octet-stream")
        return FileResponse(
            path=str(fb_task.file_path),
            filename=fb_task.clean_filename,
            media_type=content_type
        )
        
    # Check Direct task
    dir_task = direct_downloader_service.get_task(task_id)
    if dir_task and dir_task.status == "completed" and dir_task.file_path and dir_task.file_path.exists():
        return FileResponse(
            path=str(dir_task.file_path),
            filename=dir_task.clean_filename,
            media_type=dir_task.content_type or "application/octet-stream"
        )
        
    # Check disk folder
    task_dir = settings.DOWNLOADS_DIR / task_id
    if task_dir.exists():
        files = [f for f in task_dir.iterdir() if f.is_file() and f.name != ".gitkeep"]
        if files:
            target = max(files, key=lambda f: f.stat().st_size)
            ext = target.suffix.lower()
            content_type = "application/pdf" if ext == ".pdf" else ("video/mp4" if ext == ".mp4" else ("audio/mpeg" if ext == ".mp3" else "application/octet-stream"))
            return FileResponse(
                path=str(target),
                filename=target.name,
                media_type=content_type
            )
            
@app.delete("/api/task/{task_id}")
@app.post("/api/task/{task_id}/delete")
@app.post("/api/task/{task_id}/abort")
async def delete_or_abort_task(task_id: str):
    success = delete_task_files(task_id)
    return {"status": "success", "task_id": task_id, "deleted": success}


@app.get("/api/storage")
async def get_storage_info():
    return get_storage_stats()


@app.post("/api/cleanup")
async def trigger_manual_cleanup():
    res = cleanup_expired_and_abandoned_files(settings.CLEANUP_MINUTES, abandoned_max_minutes=1)
    return {"status": "success", "result": res}

