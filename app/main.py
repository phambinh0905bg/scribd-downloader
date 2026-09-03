import uuid
import json
import time
import asyncio
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any

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

templates_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))


class ScribdDownloadRequest(BaseModel):
    url: str
    pages: Optional[str] = "all"
    enable_ocr: Optional[bool] = False
    ocr_lang: Optional[str] = "vie+eng"


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


class TelegramConfigRequest(BaseModel):
    bot_token: str
    chat_id: str
    auto_send_enabled: bool = False


class CompressPdfRequest(BaseModel):
    task_id: str


class MergePdfsRequest(BaseModel):
    task_ids: List[str]
    output_filename: Optional[str] = None


class ExtractAudioRequest(BaseModel):
    task_id: str
    bitrate: Optional[str] = "320k"


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
    task = downloader_service.create_task(
        task_id, 
        url, 
        req.pages or "all", 
        enable_ocr=bool(req.enable_ocr), 
        ocr_lang=req.ocr_lang or "vie+eng"
    )
    
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
            
@app.get("/api/files")
async def list_downloaded_files():
    """List all available completed files in downloads storage with metadata, preview links and pin status."""
    downloads_dir = settings.DOWNLOADS_DIR
    if not downloads_dir.exists():
        return {"status": "success", "files": []}

    now = time.time()
    max_age_seconds = settings.CLEANUP_MINUTES * 60
    results = []

    try:
        for item in downloads_dir.iterdir():
            if not item.is_dir() or item.name in [".gitkeep", "temp"]:
                continue
            
            task_id = item.name
            is_pinned = (item / ".pinned").exists()
            
            # Find the primary completed output file
            files = [
                f for f in item.iterdir() 
                if f.is_file() and f.name not in [".gitkeep", ".pinned"] and not f.name.endswith(".part") and not f.name.endswith(".ytdl")
            ]
            if not files:
                continue
                
            main_file = max(files, key=lambda f: f.stat().st_size)
            ext = main_file.suffix.lower()
            size_bytes = main_file.stat().st_size
            mtime = main_file.stat().st_mtime
            age_seconds = now - mtime
            remaining_seconds = max(0, int(max_age_seconds - age_seconds))
            
            # Determine type & mime
            if ext == ".pdf":
                file_type = "pdf"
                content_type = "application/pdf"
            elif ext in [".mp4", ".mkv", ".webm", ".mov", ".avi"]:
                file_type = "video"
                content_type = "video/mp4"
            elif ext in [".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"]:
                file_type = "audio"
                content_type = "audio/mpeg"
            elif ext in [".zip", ".tar", ".gz", ".rar", ".7z"]:
                file_type = "archive"
                content_type = "application/zip"
            elif ext in [".jpg", ".jpeg", ".png", ".webp"]:
                file_type = "image"
                content_type = "image/jpeg"
            else:
                file_type = "file"
                content_type = "application/octet-stream"

            results.append({
                "task_id": task_id,
                "filename": main_file.name,
                "file_type": file_type,
                "content_type": content_type,
                "size_bytes": size_bytes,
                "size_mb": round(size_bytes / (1024 * 1024), 2),
                "created_at": datetime.fromtimestamp(mtime).strftime("%H:%M - %d/%m/%Y"),
                "is_pinned": is_pinned,
                "expires_in_minutes": int(remaining_seconds // 60),
                "download_url": f"/api/file/{task_id}",
                "preview_url": f"/api/files/preview/{task_id}"
            })
    except Exception as e:
        logger.error(f"Lỗi khi đọc danh sách tệp: {e}")

    # Sort newest first
    results.sort(key=lambda x: x.get("expires_in_minutes", 0), reverse=True)
    return {"status": "success", "files": results, "total_count": len(results)}


@app.post("/api/files/pin/{task_id}")
async def pin_file(task_id: str):
    """Pin a file so that auto-cleanup will NEVER delete it."""
    if not task_id or "/" in task_id or "\\" in task_id or ".." in task_id:
        raise HTTPException(status_code=400, detail="Invalid task_id")
    task_dir = settings.DOWNLOADS_DIR / task_id
    if not task_dir.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy thư mục tệp")
    
    pin_file = task_dir / ".pinned"
    pin_file.touch(exist_ok=True)
    return {"status": "success", "task_id": task_id, "is_pinned": True}


@app.post("/api/files/unpin/{task_id}")
async def unpin_file(task_id: str):
    """Unpin a file to restore normal 5-hour TTL cleanup."""
    if not task_id or "/" in task_id or "\\" in task_id or ".." in task_id:
        raise HTTPException(status_code=400, detail="Invalid task_id")
    task_dir = settings.DOWNLOADS_DIR / task_id
    if not task_dir.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy thư mục tệp")
    
    pin_file = task_dir / ".pinned"
    if pin_file.exists():
        pin_file.unlink(missing_ok=True)
    return {"status": "success", "task_id": task_id, "is_pinned": False}


@app.get("/api/files/preview/{task_id}")
async def preview_output_file(task_id: str):
    """Stream file with inline content-disposition for in-browser audio, video, and PDF preview."""
    task_dir = settings.DOWNLOADS_DIR / task_id
    if not task_dir.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp")

    files = [
        f for f in task_dir.iterdir() 
        if f.is_file() and f.name not in [".gitkeep", ".pinned"] and not f.name.endswith(".part")
    ]
    if not files:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp đã tải")

    target = max(files, key=lambda f: f.stat().st_size)
    ext = target.suffix.lower()
    
    if ext == ".pdf":
        content_type = "application/pdf"
    elif ext in [".mp4", ".mkv", ".webm", ".mov"]:
        content_type = "video/mp4"
    elif ext in [".mp3", ".m4a", ".wav", ".aac"]:
        content_type = "audio/mpeg"
    elif ext in [".jpg", ".jpeg", ".png", ".webp"]:
        content_type = "image/jpeg"
    else:
        content_type = "application/octet-stream"

    return FileResponse(
        path=str(target),
        filename=target.name,
        media_type=content_type,
        content_disposition_type="inline"
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


# --- TELEGRAM BOT ENDPOINTS ---

@app.get("/api/telegram/config")
async def get_telegram_bot_config():
    from app.telegram_bot import get_telegram_config
    cfg = get_telegram_config()
    token = cfg.get("bot_token", "")
    masked_token = f"{token[:8]}...{token[-5:]}" if len(token) > 13 else ("***" if token else "")
    return {
        "status": "success",
        "bot_token": masked_token,
        "is_configured": bool(token and cfg.get("chat_id")),
        "chat_id": cfg.get("chat_id", ""),
        "auto_send_enabled": cfg.get("auto_send_enabled", False)
    }


@app.post("/api/telegram/config")
async def save_telegram_bot_config(req: TelegramConfigRequest):
    from app.telegram_bot import save_telegram_config, get_telegram_config
    token = req.bot_token.strip()
    # If client passed masked token, keep previous token
    if "..." in token:
        old = get_telegram_config()
        token = old.get("bot_token", "")
        
    cfg = save_telegram_config(token, req.chat_id, req.auto_send_enabled)
    return {"status": "success", "message": "Đã lưu cấu hình Telegram thành công", "config": cfg}


@app.post("/api/telegram/test")
async def test_telegram_connection():
    from app.telegram_bot import send_telegram_message
    res = await send_telegram_message("🤖 <b>Media & Doc Hub</b>: Kết nối Telegram Bot thành công!")
    if res.get("success"):
        return {"status": "success", "message": "Gửi tin nhắn thử nghiệm thành công!"}
    raise HTTPException(status_code=400, detail=res.get("error", "Không thể gửi tin nhắn thử nghiệm"))


@app.post("/api/telegram/send/{task_id}")
async def send_file_to_telegram(task_id: str):
    from app.telegram_bot import send_telegram_file
    task_dir = settings.DOWNLOADS_DIR / task_id
    if not task_dir.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy thư mục tệp")
        
    files = [f for f in task_dir.iterdir() if f.is_file() and f.name not in [".gitkeep", ".pinned"] and not f.name.endswith(".part")]
    if not files:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp để gửi")
        
    target_file = max(files, key=lambda f: f.stat().st_size)
    size_mb = round(target_file.stat().st_size / (1024 * 1024), 2)
    caption = f"📦 <b>{target_file.name}</b>\n💾 Dung lượng: {size_mb} MB"
    
    res = await send_telegram_file(target_file, caption=caption)
    if res.get("success"):
        return {"status": "success", "message": f"Đã gửi tệp {target_file.name} về Telegram thành công!"}
    raise HTTPException(status_code=400, detail=res.get("error", "Lỗi gửi file lên Telegram"))


# --- QUICK PDF & MEDIA TOOLS ENDPOINTS ---

@app.post("/api/tools/compress-pdf")
async def api_compress_pdf(req: CompressPdfRequest):
    from app.tools import compress_pdf
    task_dir = settings.DOWNLOADS_DIR / req.task_id
    if not task_dir.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp")
        
    pdf_files = [f for f in task_dir.glob("*.pdf") if not f.name.startswith("compressed_")]
    if not pdf_files:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp PDF để nén")
        
    src_pdf = pdf_files[0]
    new_task_id = str(uuid.uuid4())[:8]
    new_dir = settings.DOWNLOADS_DIR / new_task_id
    new_dir.mkdir(parents=True, exist_ok=True)
    
    out_pdf = new_dir / f"compressed_{src_pdf.name}"
    res = compress_pdf(src_pdf, out_pdf)
    if res.get("success"):
        return {
            "status": "success",
            "task_id": new_task_id,
            "filename": out_pdf.name,
            "download_url": f"/api/file/{new_task_id}",
            "original_size_mb": res["original_size_mb"],
            "compressed_size_mb": res["compressed_size_mb"],
            "percentage_saved": res["percentage_saved"]
        }
    raise HTTPException(status_code=400, detail=res.get("error", "Lỗi nén PDF"))


@app.post("/api/tools/merge-pdfs")
async def api_merge_pdfs(req: MergePdfsRequest):
    from app.tools import merge_pdfs
    if len(req.task_ids) < 2:
        raise HTTPException(status_code=400, detail="Cần chọn ít nhất 2 tệp PDF để ghép")
        
    src_pdfs = []
    for tid in req.task_ids:
        t_dir = settings.DOWNLOADS_DIR / tid
        if t_dir.exists():
            pdfs = [f for f in t_dir.glob("*.pdf")]
            if pdfs:
                src_pdfs.append(pdfs[0])
                
    if len(src_pdfs) < 2:
        raise HTTPException(status_code=400, detail="Không tìm đủ 2 tệp PDF hợp lệ")
        
    new_task_id = str(uuid.uuid4())[:8]
    new_dir = settings.DOWNLOADS_DIR / new_task_id
    new_dir.mkdir(parents=True, exist_ok=True)
    
    out_name = req.output_filename.strip() if req.output_filename else f"merged_document_{new_task_id}.pdf"
    if not out_name.endswith(".pdf"):
        out_name += ".pdf"
        
    out_pdf = new_dir / out_name
    res = merge_pdfs(src_pdfs, out_pdf)
    if res.get("success"):
        return {
            "status": "success",
            "task_id": new_task_id,
            "filename": out_pdf.name,
            "download_url": f"/api/file/{new_task_id}",
            "total_files": res["total_files"],
            "total_pages": res["total_pages"],
            "size_mb": res["size_mb"]
        }
    raise HTTPException(status_code=400, detail=res.get("error", "Lỗi ghép PDF"))


@app.post("/api/tools/extract-audio")
async def api_extract_audio(req: ExtractAudioRequest):
    from app.tools import extract_audio_from_video
    task_dir = settings.DOWNLOADS_DIR / req.task_id
    if not task_dir.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp video")
        
    video_files = [f for f in task_dir.iterdir() if f.suffix.lower() in [".mp4", ".mkv", ".webm", ".mov"]]
    if not video_files:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp video trong tác vụ")
        
    src_video = video_files[0]
    new_task_id = str(uuid.uuid4())[:8]
    new_dir = settings.DOWNLOADS_DIR / new_task_id
    new_dir.mkdir(parents=True, exist_ok=True)
    
    out_mp3 = new_dir / f"{src_video.stem}.mp3"
    res = await extract_audio_from_video(src_video, out_mp3, bitrate=req.bitrate or "320k")
    if res.get("success"):
        return {
            "status": "success",
            "task_id": new_task_id,
            "filename": out_mp3.name,
            "download_url": f"/api/file/{new_task_id}",
            "size_mb": res["size_mb"]
        }
    raise HTTPException(status_code=400, detail=res.get("error", "Lỗi tách âm thanh từ video"))


