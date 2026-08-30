import re
import os
import time
import shutil
import asyncio
import logging
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

try:
    import img2pdf
except ImportError:
    img2pdf = None
from PIL import Image

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
except ImportError:
    async_playwright = None

from app.config import settings

logger = logging.getLogger("downloader")

class DownloadTask:
    def __init__(self, task_id: str, url: str, pages_range: str = "all"):
        self.task_id = task_id
        self.raw_url = url
        self.pages_range = pages_range.strip().lower()
        self.doc_id: Optional[str] = None
        self.title: str = "Tài liệu Scribd"
        self.clean_filename: str = f"scribd_{task_id}.pdf"
        
        self.status: str = "queued"  # queued, connecting, extracting, rendering, compiling, completed, failed
        self.stage_message: str = "Đang trong hàng đợi..."
        self.current_page: int = 0
        self.total_pages: int = 0
        self.target_pages: List[int] = []
        self.percentage: int = 0
        
        self.pdf_path: Optional[Path] = None
        self.pdf_size_bytes: int = 0
        self.pdf_size_mb: float = 0.0
        self.created_at: float = time.time()
        self.expires_at: float = time.time() + (settings.CLEANUP_MINUTES * 60)
        
        self.error_message: Optional[str] = None
        self.logs: List[Dict] = []
        self.subscribers: List[asyncio.Queue] = []
        
        self.task_dir = settings.DOWNLOADS_DIR / self.task_id
        self.temp_img_dir = self.task_dir / "temp_images"

    def add_log(self, message: str, level: str = "info"):
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        entry = {"time": now_str, "level": level, "message": message}
        self.logs.append(entry)
        if len(self.logs) > 200:
            self.logs.pop(0)
        self.notify_subscribers()
        logger.info(f"[{self.task_id}] {message}")

    def update_progress(self, status: str, stage_message: str, percentage: int, current_page: int = None, total_pages: int = None):
        self.status = status
        self.stage_message = stage_message
        self.percentage = max(self.percentage, max(0, min(100, percentage)))
        if current_page is not None:
            self.current_page = current_page
        if total_pages is not None:
            self.total_pages = total_pages
        self.notify_subscribers()


    def to_dict(self) -> Dict:
        remaining_seconds = max(0, int(self.expires_at - time.time()))
        return {
            "task_id": self.task_id,
            "doc_id": self.doc_id,
            "url": self.raw_url,
            "title": self.title,
            "filename": self.clean_filename,
            "status": self.status,
            "stage_message": self.stage_message,
            "current_page": self.current_page,
            "total_pages": self.total_pages,
            "target_pages_count": len(self.target_pages),
            "percentage": self.percentage,
            "pdf_size_bytes": self.pdf_size_bytes,
            "pdf_size_mb": self.pdf_size_mb,
            "download_url": f"/api/file/{self.task_id}" if self.status == "completed" else None,
            "expires_in_seconds": remaining_seconds,
            "expires_in_minutes": round(remaining_seconds / 60, 1),
            "error_message": self.error_message,
            "logs": self.logs[-50:]
        }

    def notify_subscribers(self):
        data = self.to_dict()
        for queue in self.subscribers[:]:
            try:
                queue.put_nowait(data)
            except Exception:
                pass

    def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue()
        self.subscribers.append(queue)
        queue.put_nowait(self.to_dict())
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        if queue in self.subscribers:
            self.subscribers.remove(queue)


class ScribdDownloaderService:
    def __init__(self):
        self.tasks: Dict[str, DownloadTask] = {}
        self.semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_DOWNLOADS)

    def extract_doc_id(self, url_or_id: str) -> Optional[str]:
        """Extract Scribd numeric ID from various URL patterns or pure ID."""
        url_or_id = url_or_id.strip()
        if re.fullmatch(r'\d+', url_or_id):
            return url_or_id
        
        patterns = [
            r'scribd\.com/(?:document|doc|embeds)/(\d+)',
            r'scribd\.com/presentation/(\d+)',
            r'scribd\.com/book/(\d+)',
            r'scribd\.com/audiobook/(\d+)',
            r'id=(\d+)',
            r'/(\d{6,})'
        ]
        for pattern in patterns:
            match = re.search(pattern, url_or_id, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def sanitize_filename(self, name: str) -> str:
        """Sanitize title for cross-platform filesystems."""
        clean = re.sub(r'[\\/*?:"<>|]', "", name)
        clean = re.sub(r'\s+', "_", clean).strip(" ._-")
        if not clean:
            clean = "scribd_document"
        return clean[:120]

    def parse_pages_range(self, range_str: str, total_pages: int) -> List[int]:
        """Parse page range like 'all', '1-5', '1,3,7-10'."""
        if not range_str or range_str == "all":
            return list(range(1, total_pages + 1))
        
        selected: Set[int] = set()
        parts = range_str.split(",")
        for part in parts:
            part = part.strip()
            if "-" in part:
                try:
                    start_s, end_s = part.split("-", 1)
                    start = max(1, int(start_s))
                    end = min(total_pages, int(end_s))
                    if start <= end:
                        selected.update(range(start, end + 1))
                except Exception:
                    continue
            else:
                try:
                    p = int(part)
                    if 1 <= p <= total_pages:
                        selected.add(p)
                except Exception:
                    continue
        
        result = sorted(list(selected))
        return result if result else list(range(1, total_pages + 1))

    def create_task(self, task_id: str, url: str, pages_range: str = "all") -> DownloadTask:
        task = DownloadTask(task_id, url, pages_range)
        self.tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        return self.tasks.get(task_id)

    async def run_download_task(self, task: DownloadTask):
        """Playwright-based downloader with smart waiting, auto-unblur and HD screenshotting."""
        async with self.semaphore:
            task.task_dir.mkdir(parents=True, exist_ok=True)
            task.temp_img_dir.mkdir(parents=True, exist_ok=True)
            
            task.add_log("Khởi tạo tác vụ tải tài liệu...")
            task.update_progress("connecting", "Đang phân tích liên kết Scribd...", 5)
            
            # Step 1: Extract Document ID
            doc_id = self.extract_doc_id(task.raw_url)
            if not doc_id:
                task.error_message = "Không thể nhận diện Document ID từ URL cung cấp. Vui lòng kiểm tra lại URL."
                task.add_log(f"Lỗi: {task.error_message}", level="error")
                task.update_progress("failed", task.error_message, 0)
                return
            
            task.doc_id = doc_id
            embed_url = f"https://www.scribd.com/embeds/{doc_id}/content"
            fallback_url = f"https://www.scribd.com/document/{doc_id}"
            
            task.add_log(f"Đã nhận diện Document ID: {doc_id}")
            task.add_log("Đang khởi động trình duyệt Playwright Chromium...")
            task.update_progress("connecting", "Đang khởi động Chromium...", 10)
            
            if async_playwright is None:
                task.error_message = "Playwright không được cài đặt trong môi trường."
                task.add_log(f"Lỗi: {task.error_message}", level="error")
                task.update_progress("failed", task.error_message, 0)
                return

            try:
                # Ensure temporary directory exists before launching Playwright
                settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
                task.task_dir.mkdir(parents=True, exist_ok=True)
                
                async with async_playwright() as p:
                    # Clean Docker Chromium args (NO single-process, NO no-zygote)
                    browser: Browser = await p.chromium.launch(

                        headless=True,
                        args=[
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-gpu",
                            "--disable-blink-features=AutomationControlled"
                        ]
                    )
                    task.add_log("Trình duyệt Chromium đã sẵn sàng.")
                    
                    context: BrowserContext = await browser.new_context(
                        viewport={"width": 1280, "height": 1800},
                        device_scale_factor=settings.DEVICE_SCALE_FACTOR,
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                        locale="en-US",
                        timezone_id="America/New_York"
                    )

                    
                    # Bypass anti-bot and headless detection
                    await context.add_init_script("""
                    () => {
                        // 1. Remove webdriver
                        delete Object.getPrototypeOf(navigator).webdriver;
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

                        // 2. Mock chrome object
                        window.chrome = {
                            app: { isInstalled: false },
                            runtime: {
                                connect: () => {},
                                sendMessage: () => {}
                            }
                        };

                        // 3. Mock languages & platform
                        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
                        Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
                        Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

                        // 4. Mock Plugins
                        Object.defineProperty(navigator, 'plugins', {
                            get: () => [
                                { name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                                { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                                { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }
                            ]
                        });

                        // 5. Mock WebGL Vendor & Renderer
                        const getParameter = WebGLRenderingContext.prototype.getParameter;
                        WebGLRenderingContext.prototype.getParameter = function(parameter) {
                            if (parameter === 37445) return 'Google Inc. (Intel)';
                            if (parameter === 37446) return 'ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)';
                            return getParameter.apply(this, arguments);
                        };

                        // 6. Mock Permissions
                        if (navigator.permissions && navigator.permissions.query) {
                            const origQuery = navigator.permissions.query;
                            navigator.permissions.query = (parameters) => (
                                parameters.name === 'notifications' ?
                                    Promise.resolve({ state: Notification.permission || 'default' }) :
                                    origQuery(parameters)
                            );
                        }
                    }
                    """)

                    
                    page: Page = await context.new_page()
                    page.set_default_timeout(35000)

                    async def wait_for_scribd_challenge(p_page: Page, p_task: DownloadTask):
                        for i in range(15):
                            try:
                                title = await p_page.title()
                                if any(kw in title.lower() for kw in ["client challenge", "just a moment", "checking your browser", "attention required", "cloudflare"]):
                                    if i == 0 or i % 4 == 0:
                                        p_task.add_log("Đang vượt tường lửa xác thực Cloudflare của Scribd...")
                                    await asyncio.sleep(1.0)
                                else:
                                    break
                            except Exception:
                                await asyncio.sleep(1.0)

                    try:
                        task.update_progress("connecting", "Đang kết nối tới máy chủ Scribd...", 15)
                        task.add_log(f"Đang tải trang embed: {embed_url}")
                        
                        target_url = embed_url
                        try:
                            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                        except Exception as nav_err:
                            task.add_log(f"Embed URL gặp lỗi ({nav_err}), thử chuyển sang link document trực tiếp...", level="warning")
                            target_url = fallback_url
                            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                        
                        await wait_for_scribd_challenge(page, task)
                        
                        task.add_log("Đang chờ trình xem tài liệu tải xong các trang...")
                        try:
                            await page.wait_for_selector(".outer_page, div[id^='outer_page_']", timeout=20000)
                        except Exception:
                            pass
                            
                        await asyncio.sleep(1.0)
                        
                        # Step 3: Extract Metadata & Unblur
                        task.update_progress("extracting", "Đang phân tích cấu trúc tài liệu...", 22)
                        
                        # JS unblur and remove overlays
                        unblur_script = """
                        () => {
                            // 1. Remove all blur and hidden classes
                            document.querySelectorAll('.page_blur, .page_missing, .blurred_page, .blurred, .missing_page, .not_visible').forEach(el => {
                                el.classList.remove('page_blur', 'page_missing', 'blurred_page', 'blurred', 'missing_page', 'not_visible');
                                el.style.filter = 'none';
                                el.style.opacity = '1';
                                el.style.display = 'block';
                            });
                            
                            // 2. Hide toolbar, promo banners, overlays
                            document.querySelectorAll('.toolbar, .toolbar_drop, .auto__embeds_new_toolbar, .promo_wrapper, .between_page_module, .auto_archive_container, .between_page_portal_root, .mobile_banner, .banner, .ad_unit, .global_header, .global_footer, .lightbox, .overlay').forEach(el => {
                                el.style.display = 'none';
                            });
                            
                            // 3. Extract title
                            let docTitle = document.querySelector('.toolbar_title')?.innerText ||
                                           document.querySelector('h1')?.innerText ||
                                           document.querySelector('.document_title')?.innerText || 
                                           document.querySelector('.title')?.innerText || 
                                           document.querySelector('meta[property="og:title"]')?.getAttribute('content') ||
                                           document.title || 
                                           '';
                            
                            let pages = document.querySelectorAll('.outer_page, div[id^="outer_page_"]');
                            return {
                                title: docTitle.trim(),
                                pageCount: pages.length
                            };
                        }
                        """
                        meta = await page.evaluate(unblur_script)
                        
                        # Extract title
                        raw_title = meta.get("title") or ""
                        if not raw_title or raw_title.lower() in ["scribd", "client challenge"]:
                            slug_match = re.search(r'/document/\d+/([^/?#]+)', task.raw_url)
                            if slug_match:
                                slug_name = slug_match.group(1).replace('-', ' ').replace('_', ' ').strip().title()
                                if slug_name and slug_name.lower() not in ["pdf", "download", "doc"]:
                                    raw_title = slug_name
                                    
                        raw_title = re.sub(r'\|\s*Scribd.*$', '', raw_title, flags=re.IGNORECASE).strip()
                        raw_title = re.sub(r'\|\s*PDF.*$', '', raw_title, flags=re.IGNORECASE).strip()
                        if not raw_title or raw_title.lower() in ["scribd", "client challenge"]:
                            raw_title = f"Scribd_Document_{doc_id}"
                        
                        task.title = raw_title
                        safe_name = self.sanitize_filename(raw_title)
                        task.clean_filename = f"{safe_name}.pdf"
                        task.add_log(f"Tiêu đề tài liệu: \"{task.title}\"")
                        
                        page_elements = await page.query_selector_all(".outer_page, div[id^='outer_page_']")
                        total_pages_detected = len(page_elements)
                        
                        # Fallback to direct document page if embed had 0 pages
                        if total_pages_detected == 0 and target_url != fallback_url:
                            task.add_log(f"Chuyển sang trang tài liệu chính: {fallback_url}...", level="warning")
                            try:
                                await page.goto(fallback_url, wait_until="domcontentloaded", timeout=20000)
                                await wait_for_scribd_challenge(page, task)
                                await page.wait_for_selector(".outer_page, div[id^='outer_page_']", timeout=15000)
                                await asyncio.sleep(1.0)
                                await page.evaluate(unblur_script)
                                page_elements = await page.query_selector_all(".outer_page, div[id^='outer_page_']")
                                total_pages_detected = len(page_elements)
                            except Exception:
                                pass





                        
                        if total_pages_detected == 0:
                            task.error_message = "Không tìm thấy trang nào trong tài liệu này (có thể tài liệu đã bị xóa hoặc ở chế độ riêng tư)."
                            task.add_log(f"Lỗi: {task.error_message}", level="error")
                            task.update_progress("failed", task.error_message, 0)
                            return
                        
                        task.total_pages = total_pages_detected
                        task.target_pages = self.parse_pages_range(task.pages_range, total_pages_detected)
                        total_target = len(task.target_pages)
                        
                        task.add_log(f"Đã phát hiện tổng cộng {total_pages_detected} trang. Số trang cần tải: {total_target}")
                        task.update_progress("rendering", f"Bắt đầu chụp {total_target} trang chất lượng cao...", 30)

                        
                        # Step 4: Capture HD Screenshots
                        captured_images = []
                        
                        for idx, page_num in enumerate(task.target_pages, start=1):
                            task.current_page = page_num
                            
                            # Calculate rendering progress between 30% -> 85%
                            progress_pct = 30 + int((idx / total_target) * 55)
                            stage_msg = f"Đang chụp trang {idx}/{total_target} (Trang gốc #{page_num})..."
                            task.update_progress("rendering", stage_msg, progress_pct)
                            task.add_log(f"Đang xử lý trang {page_num}...")
                            
                            # Find element for this page
                            element = await page.query_selector(f"#outer_page_{page_num}")
                            if not element:
                                element = await page.query_selector(f"#page{page_num}")
                            if not element:
                                element = await page.query_selector(f"div[data-page-number='{page_num}']")
                            if not element:
                                if page_num - 1 < len(page_elements):
                                    element = page_elements[page_num - 1]
                            
                            if not element:
                                task.add_log(f"Cảnh báo: Thử cuộn tìm phần tử trang {page_num}...", level="warning")
                                await page.evaluate(f"window.scrollTo(0, (document.body.scrollHeight / {total_pages_detected}) * {page_num - 1});")
                                await asyncio.sleep(0.5)
                                element = await page.query_selector(f"#outer_page_{page_num}") or await page.query_selector(f"#page{page_num}")
                            
                            img_path = task.temp_img_dir / f"page_{page_num:04d}.png"
                            
                            if element:
                                try:
                                    await element.scroll_into_view_if_needed()
                                    await page.evaluate("""
                                    (el) => {
                                        el.classList.remove('page_blur', 'page_missing', 'blurred_page', 'blurred', 'missing_page');
                                        el.style.filter = 'none';
                                        el.style.opacity = '1';
                                        el.style.display = 'block';
                                        
                                        el.querySelectorAll('img').forEach(img => {
                                            img.style.filter = 'none';
                                            img.style.opacity = '1';
                                            img.style.visibility = 'visible';
                                        });
                                    }
                                    """, element)
                                    
                                    await asyncio.sleep(0.3)
                                    await element.screenshot(path=str(img_path), type="jpeg", quality=95)
                                    if img_path.exists() and img_path.stat().st_size > 0:
                                        captured_images.append(img_path)
                                        task.add_log(f"✅ Đã chụp trang #{page_num} ({round(img_path.stat().st_size / 1024, 1)} KB)")
                                except Exception as snap_err:
                                    task.add_log(f"Lỗi chụp phần tử trang {page_num}: {snap_err}. Thử chụp khung nhìn...", level="warning")
                                    await page.screenshot(path=str(img_path), type="jpeg", quality=95)
                                    captured_images.append(img_path)
                            else:
                                task.add_log(f"Không thể định vị trang {page_num}, chụp màn hình hiện tại...", level="warning")
                                await page.screenshot(path=str(img_path), type="jpeg", quality=95)
                                captured_images.append(img_path)

                                task.add_log(f"Bỏ qua trang {page_num} do không tìm thấy thẻ DOM.", level="warning")
                        
                        if not captured_images:
                            task.error_message = "Không trích xuất được hình ảnh nào từ tài liệu."
                            task.add_log(f"Lỗi: {task.error_message}", level="error")
                            task.update_progress("failed", task.error_message, 0)
                            return
                        
                        # Step 5: Compile Images into PDF
                        total_imgs = len(captured_images)
                        task.update_progress("compiling", f"Bắt đầu đóng gói {total_imgs} trang thành file PDF...", 88)
                        task.add_log(f"📦 Bắt đầu tiến trình ghép nối {total_imgs} trang ảnh sang file PDF...")
                        
                        output_pdf = task.task_dir / task.clean_filename
                        pdf_created = False
                        
                        # Try high-speed direct stream merge with img2pdf
                        if img2pdf is not None:
                            try:
                                task.add_log(f"Đang phân tích và tối ưu hóa {total_imgs} tệp ảnh...")
                                task.update_progress("compiling", f"Đang ghép trực tiếp {total_imgs} luồng ảnh vào PDF...", 92)
                                await asyncio.sleep(0.1)
                                
                                def convert_img2pdf():
                                    with open(output_pdf, "wb") as f:
                                        f.write(img2pdf.convert([str(p) for p in captured_images]))
                                
                                task.add_log("Đang ghi cấu trúc trang và mục lục PDF siêu tốc...")
                                await asyncio.to_thread(convert_img2pdf)
                                pdf_created = True
                                task.add_log("✅ Đã hoàn tất đóng gói dữ liệu qua img2pdf.")
                                task.update_progress("compiling", "Đang hoàn tất lưu trữ file PDF...", 98)
                            except Exception as e:
                                task.add_log(f"Cảnh báo img2pdf ({e}), chuyển sang chế độ ghép dự phòng bằng Pillow...", level="warning")
                        
                        if not pdf_created:
                            task.add_log(f"Bắt đầu xử lý từng khối trang bằng Pillow ({total_imgs} trang)...")
                            
                            # Batch progress simulation for UI feedback
                            batch_size = max(5, total_imgs // 10)
                            for b_idx in range(0, total_imgs, batch_size):
                                curr_batch = min(b_idx + batch_size, total_imgs)
                                pct = 90 + int((curr_batch / total_imgs) * 8)
                                task.update_progress("compiling", f"Đang nén & ghép trang {curr_batch}/{total_imgs}...", pct)
                                task.add_log(f"  ↳ Đã tối ưu định dạng trang {curr_batch}/{total_imgs}...")
                                await asyncio.sleep(0.05)
                            
                            def convert_pillow():
                                pil_images = [Image.open(img_path).convert("RGB") for img_path in captured_images]
                                if pil_images:
                                    pil_images[0].save(output_pdf, save_all=True, append_images=pil_images[1:], resolution=150.0)
                            
                            task.add_log("Đang nén và xuất file PDF hoàn chỉnh...")
                            await asyncio.to_thread(convert_pillow)
                            task.add_log("✅ Đã hoàn tất xuất file PDF qua Pillow.")
                        
                        if not output_pdf.exists() or output_pdf.stat().st_size == 0:
                            task.error_message = "Lỗi khi tạo file PDF cuối cùng."
                            task.add_log(f"Lỗi: {task.error_message}", level="error")
                            task.update_progress("failed", task.error_message, 0)
                            return
                        
                        # Clean up temp image files
                        task.add_log("Đang dọn dẹp các tệp ảnh tạm thời để giải phóng dung lượng...")
                        shutil.rmtree(task.temp_img_dir, ignore_errors=True)
                        
                        task.pdf_path = output_pdf
                        task.pdf_size_bytes = output_pdf.stat().st_size
                        task.pdf_size_mb = round(task.pdf_size_bytes / (1024 * 1024), 2)
                        
                        task.add_log(f"🎉 Xuất file PDF thành công: {task.clean_filename} (Dung lượng: {task.pdf_size_mb} MB).")
                        task.add_log(f"⏰ File sẽ tự động lưu trữ và xóa sau {settings.CLEANUP_MINUTES} phút.")
                        task.update_progress("completed", f"Hoàn tất! File PDF ({task.pdf_size_mb} MB) đã sẵn sàng tải xuống.", 100)

                        
                    except Exception as e:
                        task.error_message = f"Xảy ra lỗi trong quá trình xử lý: {str(e)}"
                        task.add_log(f"Lỗi ngoại lệ: {str(e)}", level="error")
                        task.update_progress("failed", task.error_message, 0)
                    finally:
                        await context.close()
                        await browser.close()
            except Exception as outer_err:
                task.error_message = f"Lỗi khởi chạy Playwright: {str(outer_err)}"
                task.add_log(f"Lỗi Playwright: {str(outer_err)}", level="error")
                task.update_progress("failed", task.error_message, 0)

downloader_service = ScribdDownloaderService()
