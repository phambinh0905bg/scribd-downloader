import uuid
import json
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl

from app.config import settings
from app.downloader import downloader_service, DownloadTask
from app.cleanup import start_cleanup_scheduler, cleanup_expired_files, get_storage_stats

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: start cleanup scheduler
    cleanup_task = asyncio.create_task(start_cleanup_scheduler())
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} started on port {settings.PORT}")
    yield
    # Shutdown
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


class DownloadRequest(BaseModel):
    url: str
    pages: Optional[str] = "all"


@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.APP_NAME,
            "app_version": settings.APP_VERSION,
            "cleanup_minutes": settings.CLEANUP_MINUTES
        }
    )



@app.post("/api/download")
async def start_download(req: DownloadRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Vui lòng nhập đường dẫn URL tài liệu Scribd.")
    
    doc_id = downloader_service.extract_doc_id(url)
    if not doc_id:
        raise HTTPException(status_code=400, detail="URL không hợp lệ hoặc không tìm thấy ID tài liệu Scribd.")
    
    task_id = str(uuid.uuid4())[:8]
    task = downloader_service.create_task(task_id, url, req.pages or "all")
    
    # Launch task in background
    asyncio.create_task(downloader_service.run_download_task(task))
    
    return {
        "status": "success",
        "task_id": task_id,
        "doc_id": doc_id,
        "message": "Đã khởi tạo tác vụ tải tài liệu."
    }


@app.get("/api/status/{task_id}")
async def get_task_status(task_id: str):
    task = downloader_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ tải hoặc tác vụ đã hết hạn.")
    return task.to_dict()


@app.get("/api/stream/{task_id}")
async def stream_task_progress(task_id: str):
    """Server-Sent Events (SSE) stream for real-time progress updates."""
    task = downloader_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ tải.")

    async def event_generator():
        queue = task.subscribe()
        try:
            while True:
                try:
                    # Wait for next update or heartbeat
                    data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    
                    if data.get("status") in ["completed", "failed"]:
                        # Send final event and close stream
                        await asyncio.sleep(0.5)
                        break
                except asyncio.TimeoutError:
                    # Send heartbeat ping to keep connection alive
                    yield ": ping\n\n"
        finally:
            task.unsubscribe(queue)

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
async def download_pdf_file(task_id: str):
    task = downloader_service.get_task(task_id)
    if not task or task.status != "completed" or not task.pdf_path or not task.pdf_path.exists():
        # Check if file still exists in downloads folder
        task_dir = settings.DOWNLOADS_DIR / task_id
        if task_dir.exists():
            pdfs = list(task_dir.glob("*.pdf"))
            if pdfs and pdfs[0].exists():
                return FileResponse(
                    path=str(pdfs[0]),
                    filename=pdfs[0].name,
                    media_type="application/pdf"
                )
        raise HTTPException(status_code=404, detail="File PDF không tồn tại hoặc đã bị dọn dẹp tự động.")
    
    return FileResponse(
        path=str(task.pdf_path),
        filename=task.clean_filename,
        media_type="application/pdf"
    )


@app.get("/api/storage")
async def get_storage_info():
    return get_storage_stats()


@app.post("/api/cleanup")
async def trigger_manual_cleanup():
    res = cleanup_expired_files(settings.CLEANUP_MINUTES)
    return {"status": "success", "result": res}
