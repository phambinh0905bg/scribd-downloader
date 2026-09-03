import os
import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Callable
import pikepdf

logger = logging.getLogger("ocr")

async def convert_images_to_searchable_pdf(
    image_paths: List[Path],
    output_pdf_path: Path,
    lang: str = "vie+eng",
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> bool:
    """
    Run Tesseract OCR on list of images to generate a searchable PDF with invisible text layer.
    Uses pikepdf to merge all generated OCR page PDFs into the final document.
    """
    if not image_paths:
        return False

    temp_pdf_pages: List[Path] = []
    temp_dir = output_pdf_path.parent / "ocr_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    sem = asyncio.Semaphore(4)  # Limit concurrent tesseract workers to prevent CPU overload

    async def ocr_single_image(idx: int, img_path: Path):
        async with sem:
            out_base = temp_dir / f"page_{idx:04d}"
            expected_pdf = temp_dir / f"page_{idx:04d}.pdf"
            
            cmd = [
                "tesseract",
                str(img_path),
                str(out_base),
                "pdf",
                "-l",
                lang,
                "--oem",
                "1"
            ]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await proc.wait()
                if expected_pdf.exists() and expected_pdf.stat().st_size > 0:
                    return idx, expected_pdf
            except Exception as e:
                logger.warning(f"Lỗi chạy OCR trang {idx}: {e}")
            return idx, None

    try:
        tasks = [ocr_single_image(i, p) for i, p in enumerate(image_paths, start=1)]
        total = len(tasks)
        completed_pages = 0

        results = []
        for f in asyncio.as_completed(tasks):
            res = await f
            results.append(res)
            completed_pages += 1
            if progress_callback:
                progress_callback(completed_pages, total)

        # Sort pages back by original order
        results.sort(key=lambda x: x[0])
        valid_page_pdfs = [p for _, p in results if p is not None and p.exists()]

        if not valid_page_pdfs:
            logger.error("Không có trang OCR nào được tạo thành công.")
            return False

        # Merge with pikepdf
        def merge_ocr():
            merged_pdf = pikepdf.Pdf.new()
            for page_pdf_path in valid_page_pdfs:
                try:
                    with pikepdf.open(page_pdf_path) as src:
                        merged_pdf.pages.extend(src.pages)
                except Exception as merge_err:
                    logger.warning(f"Lỗi ghép trang OCR {page_pdf_path}: {merge_err}")
            merged_pdf.save(output_pdf_path)

        await asyncio.to_thread(merge_ocr)
        logger.info(f"✅ Hoàn tất tạo Searchable PDF với OCR ({len(valid_page_pdfs)} trang): {output_pdf_path.name}")
        return True

    except Exception as e:
        logger.error(f"Lỗi trong quá trình OCR PDF: {e}")
        return False
    finally:
        try:
            for item in temp_dir.glob("*"):
                item.unlink(missing_ok=True)
            temp_dir.rmdir()
        except Exception:
            pass