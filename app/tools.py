import os
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any
import pikepdf

logger = logging.getLogger("tools")

def compress_pdf(input_path: Path, output_path: Path) -> Dict[str, Any]:
    """Compress PDF using pikepdf by recompressing streams and removing duplicated resources."""
    if not input_path.exists():
        return {"success": False, "error": "Tệp đầu vào không tồn tại"}

    original_size = input_path.stat().st_size
    try:
        with pikepdf.open(input_path) as pdf:
            pdf.save(
                output_path,
                compress_streams=True,
                recompress_flate=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
                linearize=True
            )
        new_size = output_path.stat().st_size
        saved_bytes = max(0, original_size - new_size)
        pct_saved = round((saved_bytes / original_size) * 100, 1) if original_size > 0 else 0
        
        return {
            "success": True,
            "original_size": original_size,
            "compressed_size": new_size,
            "original_size_mb": round(original_size / (1024 * 1024), 2),
            "compressed_size_mb": round(new_size / (1024 * 1024), 2),
            "saved_bytes": saved_bytes,
            "percentage_saved": pct_saved,
            "output_filename": output_path.name
        }
    except Exception as e:
        logger.error(f"Lỗi nén PDF {input_path.name}: {e}")
        return {"success": False, "error": str(e)}

def merge_pdfs(pdf_paths: List[Path], output_path: Path) -> Dict[str, Any]:
    """Merge multiple PDF files into one using pikepdf."""
    valid_paths = [p for p in pdf_paths if p.exists() and p.is_file()]
    if len(valid_paths) < 2:
        return {"success": False, "error": "Cần ít nhất 2 tệp PDF hợp lệ để ghép"}

    try:
        merged = pikepdf.Pdf.new()
        total_pages = 0
        for p in valid_paths:
            with pikepdf.open(p) as src:
                merged.pages.extend(src.pages)
                total_pages += len(src.pages)
                
        merged.save(output_path, compress_streams=True)
        return {
            "success": True,
            "total_files": len(valid_paths),
            "total_pages": total_pages,
            "output_filename": output_path.name,
            "size_mb": round(output_path.stat().st_size / (1024 * 1024), 2)
        }
    except Exception as e:
        logger.error(f"Lỗi ghép PDF: {e}")
        return {"success": False, "error": str(e)}

def split_pdf(input_path: Path, output_dir: Path, page_range_str: str) -> Dict[str, Any]:
    """Split PDF into selected pages or page ranges using pikepdf."""
    if not input_path.exists():
        return {"success": False, "error": "Tệp PDF gốc không tồn tại"}

    try:
        with pikepdf.open(input_path) as src:
            total_pages = len(src.pages)
            selected_indices = set()
            
            # Parse page range string e.g. "1-3, 5, 8-10" or "all"
            clean_str = page_range_str.strip().lower()
            if not clean_str or clean_str == "all":
                selected_indices = set(range(total_pages))
            else:
                parts = [p.strip() for p in clean_str.split(",") if p.strip()]
                for p in parts:
                    if "-" in p:
                        subparts = p.split("-")
                        if len(subparts) == 2 and subparts[0].isdigit() and subparts[1].isdigit():
                            start_p = max(1, int(subparts[0]))
                            end_p = min(total_pages, int(subparts[1]))
                            for idx in range(start_p - 1, end_p):
                                selected_indices.add(idx)
                    elif p.isdigit():
                        p_num = int(p)
                        if 1 <= p_num <= total_pages:
                            selected_indices.add(p_num - 1)

            if not selected_indices:
                return {"success": False, "error": f"Không có trang hợp lệ được chọn (tổng số trang: {total_pages})"}

            sorted_indices = sorted(list(selected_indices))
            dst = pikepdf.Pdf.new()
            for idx in sorted_indices:
                dst.pages.append(src.pages[idx])

            output_dir.mkdir(parents=True, exist_ok=True)
            out_filename = f"split_{input_path.stem}.pdf"
            out_path = output_dir / out_filename
            dst.save(out_path, compress_streams=True)

            return {
                "success": True,
                "total_source_pages": total_pages,
                "extracted_pages": len(sorted_indices),
                "output_filename": out_filename,
                "size_mb": round(out_path.stat().st_size / (1024 * 1024), 2)
            }
    except Exception as e:
        logger.error(f"Lỗi tách trang PDF {input_path.name}: {e}")
        return {"success": False, "error": str(e)}

async def extract_audio_from_video(video_path: Path, output_path: Path, bitrate: str = "320k") -> Dict[str, Any]:
    """Extract audio from video file using ffmpeg."""
    if not video_path.exists():
        return {"success": False, "error": "Tệp video không tồn tại"}

    cmd = [
        "ffmpeg",
        "-y",
        "-threads", "0",
        "-i", str(video_path),
        "-vn",
        "-c:a", "libmp3lame",
        "-b:a", bitrate,
        "-compression_level", "0",
        str(output_path)
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.wait()
        if output_path.exists() and output_path.stat().st_size > 0:
            return {
                "success": True,
                "output_filename": output_path.name,
                "size_mb": round(output_path.stat().st_size / (1024 * 1024), 2)
            }
        return {"success": False, "error": "Không trích xuất được âm thanh từ video"}
    except Exception as e:
        logger.error(f"Lỗi extract audio: {e}")
        return {"success": False, "error": str(e)}