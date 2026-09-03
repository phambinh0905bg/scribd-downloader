import io
import re
import base64
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps, ImageEnhance
import qrcode
import qrcode.image.svg
import barcode
from barcode.writer import ImageWriter, SVGWriter
import zxingcpp

logger = logging.getLogger("barcode")

SUPPORTED_1D_FORMATS = {
    "code128": "Code 128 (Mã vạch chuẩn đa năng)",
    "code39": "Code 39 (Chữ in hoa & Số)",
    "ean13": "EAN-13 (Hàng hoá quốc tế 13 số)",
    "ean8": "EAN-8 (Hàng hoá nhỏ 8 số)",
    "upca": "UPC-A (Hàng hoá chuẩn Mỹ 12 số)",
    "isbn13": "ISBN-13 (Sách & Ấn phẩm)",
    "isbn10": "ISBN-10 (Sách cũ)",
    "issn": "ISSN (Tạp chí & Định kỳ)",
    "pzn": "PZN (Dược phẩm)"
}

SUPPORTED_2D_FORMATS = {
    "qrcode": "QR Code (Mã phản hồi nhanh)",
}

def parse_barcode_content(raw_text: str) -> Dict[str, Any]:
    """Analyze barcode content to identify URLs, Wi-Fi configs, vCards, etc."""
    text = raw_text.strip()
    
    # 1. URL
    if re.match(r"^https?://", text, re.IGNORECASE):
        return {
            "type": "url",
            "title": "Liên kết Website",
            "url": text,
            "action_text": "Mở liên kết"
        }
        
    # 2. Wi-Fi: WIFI:S:MySSID;T:WPA;P:MyPassword;;
    wifi_match = re.match(r"^WIFI:(.*?);;?$", text, re.IGNORECASE)
    if wifi_match:
        fields = {}
        for part in wifi_match.group(1).split(";"):
            if ":" in part:
                k, v = part.split(":", 1)
                fields[k.upper()] = v
        ssid = fields.get("S", "")
        password = fields.get("P", "")
        auth_type = fields.get("T", "WPA/WPA2")
        hidden = fields.get("H", "false").lower() in ("true", "1")
        return {
            "type": "wifi",
            "title": "Mạng Wi-Fi",
            "ssid": ssid,
            "password": password,
            "auth_type": auth_type,
            "hidden": hidden,
            "action_text": "Sao chép mật khẩu Wi-Fi"
        }
        
    # 3. vCard / MeCard
    if "BEGIN:VCARD" in text.upper() or text.upper().startswith("MECARD:"):
        name_match = re.search(r"(?:FN|N):([^\r\n;]+)", text, re.IGNORECASE)
        tel_match = re.search(r"TEL(?:;[^\r\n:]+)?:([^\r\n;]+)", text, re.IGNORECASE)
        email_match = re.search(r"EMAIL(?:;[^\r\n:]+)?:([^\r\n;]+)", text, re.IGNORECASE)
        org_match = re.search(r"ORG:([^\r\n;]+)", text, re.IGNORECASE)
        return {
            "type": "contact",
            "title": "Danh bạ liên hệ",
            "name": name_match.group(1).strip() if name_match else "",
            "tel": tel_match.group(1).strip() if tel_match else "",
            "email": email_match.group(1).strip() if email_match else "",
            "org": org_match.group(1).strip() if org_match else "",
            "action_text": "Lưu danh bạ"
        }
        
    # 4. Email: mailto:test@example.com?subject=...
    if text.lower().startswith("mailto:"):
        email = text[7:].split("?")[0]
        return {
            "type": "email",
            "title": "Địa chỉ Email",
            "email": email,
            "action_text": "Gửi Email"
        }
        
    # 5. Telephone: tel:+84987654321
    if text.lower().startswith("tel:"):
        phone = text[4:]
        return {
            "type": "phone",
            "title": "Số điện thoại",
            "phone": phone,
            "action_text": "Gọi số"
        }
        
    # 6. Geo location: geo:10.762622,106.660172
    if text.lower().startswith("geo:"):
        coords = text[4:].split("?")[0]
        return {
            "type": "geo",
            "title": "Toạ độ vị trí (Bản đồ)",
            "coords": coords,
            "url": f"https://www.google.com/maps/search/?api=1&query={coords}",
            "action_text": "Xem trên bản đồ"
        }
        
    return {
        "type": "text",
        "title": "Văn bản thô",
        "action_text": "Sao chép"
    }


def generate_barcode(
    content: str,
    barcode_type: str = "qrcode",
    fg_color: str = "#000000",
    bg_color: str = "#ffffff",
    ec_level: str = "M",
    scale: int = 4,
    show_text: bool = True
) -> Dict[str, Any]:
    """
    Generate 1D barcode or 2D QR Code.
    Returns dict containing base64 data URI, svg string (if available), format and dimensions.
    """
    if not content:
        raise ValueError("Nội dung tạo mã không được để trống")

    barcode_type_lower = barcode_type.lower().strip()

    # Case 1: 2D QR Code
    if barcode_type_lower in ("qrcode", "qr"):
        ec_map = {
            "L": qrcode.constants.ERROR_CORRECT_L,
            "M": qrcode.constants.ERROR_CORRECT_M,
            "Q": qrcode.constants.ERROR_CORRECT_Q,
            "H": qrcode.constants.ERROR_CORRECT_H
        }
        error_correction = ec_map.get(ec_level.upper(), qrcode.constants.ERROR_CORRECT_M)

        qr = qrcode.QRCode(
            version=None,
            error_correction=error_correction,
            box_size=max(2, min(scale * 3, 30)),
            border=2
        )
        qr.add_data(content)
        qr.make(fit=True)

        # PNG Image
        pil_img = qr.make_image(fill_color=fg_color, back_color=bg_color).get_image()
        # Ensure RGB mode for PNG output
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")

        buffer = io.BytesIO()
        pil_img.save(buffer, format="PNG")
        png_bytes = buffer.getvalue()
        png_b64 = base64.b64encode(png_bytes).decode("utf-8")

        # SVG Generation
        svg_buffer = io.BytesIO()
        svg_factory = qrcode.image.svg.SvgPathImage
        svg_img = qr.make_image(image_factory=svg_factory, fill_color=fg_color, back_color=bg_color)
        svg_img.save(svg_buffer)
        svg_string = svg_buffer.getvalue().decode("utf-8")

        return {
            "success": True,
            "barcode_type": "qrcode",
            "format_name": "QR Code",
            "is_2d": True,
            "width": pil_img.width,
            "height": pil_img.height,
            "data_url": f"data:image/png;base64,{png_b64}",
            "svg": svg_string,
            "content": content
        }

    # Case 2: 1D Barcode
    if barcode_type_lower not in SUPPORTED_1D_FORMATS:
        barcode_type_lower = "code128"

    barcode_class = barcode.get_barcode_class(barcode_type_lower)
    
    # Specific validation for EAN-13, EAN-8, UPC-A
    sanitized_content = content.strip()
    if barcode_type_lower in ("ean13", "ean8", "upca"):
        # Remove non-digits
        digits_only = re.sub(r"\D", "", sanitized_content)
        if barcode_type_lower == "ean13" and len(digits_only) not in (12, 13):
            raise ValueError("EAN-13 yêu cầu 12 hoặc 13 chữ số")
        if barcode_type_lower == "ean8" and len(digits_only) not in (7, 8):
            raise ValueError("EAN-8 yêu cầu 7 hoặc 8 chữ số")
        if barcode_type_lower == "upca" and len(digits_only) not in (11, 12):
            raise ValueError("UPC-A yêu cầu 11 hoặc 12 chữ số")
        sanitized_content = digits_only

    writer_options = {
        "module_width": max(0.2, scale * 0.1),
        "module_height": max(10.0, scale * 4.0),
        "quiet_zone": 3.0,
        "foreground": fg_color,
        "background": bg_color,
        "write_text": show_text,
        "font_size": max(7, scale * 2),
        "text_distance": 3.0
    }

    try:
        bc_obj = barcode_class(sanitized_content, writer=ImageWriter())
        img_buffer = io.BytesIO()
        bc_obj.write(img_buffer, options=writer_options)
        img_buffer.seek(0)
        pil_img = Image.open(img_buffer)
        
        # Save clean PNG
        out_buf = io.BytesIO()
        pil_img.save(out_buf, format="PNG")
        png_bytes = out_buf.getvalue()
        png_b64 = base64.b64encode(png_bytes).decode("utf-8")

        # Generate SVG
        svg_buffer = io.BytesIO()
        svg_bc_obj = barcode_class(sanitized_content, writer=SVGWriter())
        svg_bc_obj.write(svg_buffer, options=writer_options)
        svg_string = svg_buffer.getvalue().decode("utf-8")

        return {
            "success": True,
            "barcode_type": barcode_type_lower,
            "format_name": SUPPORTED_1D_FORMATS.get(barcode_type_lower, barcode_type_lower.upper()),
            "is_2d": False,
            "width": pil_img.width,
            "height": pil_img.height,
            "data_url": f"data:image/png;base64,{png_b64}",
            "svg": svg_string,
            "content": sanitized_content
        }
    except Exception as e:
        logger.error(f"Lỗi tạo mã vạch {barcode_type_lower}: {e}")
        raise ValueError(f"Không thể tạo mã vạch: {str(e)}")


def decode_barcode_image(image_input: Union[bytes, Path, Image.Image]) -> Dict[str, Any]:
    """
    Decode any 1D Barcodes and 2D QR Codes from image.
    Accepts raw image bytes, Path to image file, or PIL.Image instance.
    Returns detected barcodes, bounding boxes, highlighted annotated image data, and parsed metadata.
    """
    # 1. Load PIL Image
    if isinstance(image_input, Image.Image):
        pil_img = image_input
    elif isinstance(image_input, (str, Path)):
        pil_img = Image.open(image_input)
    elif isinstance(image_input, bytes):
        pil_img = Image.open(io.BytesIO(image_input))
    else:
        raise ValueError("Định dạng ảnh đầu vào không hợp lệ")

    # Transpose EXIF orientation if needed
    try:
        pil_img = ImageOps.exif_transpose(pil_img)
    except Exception:
        pass

    # Ensure in RGB
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")

    orig_width, orig_height = pil_img.size

    # First pass: read directly
    results = zxingcpp.read_barcodes(pil_img)

    # Second pass: if no barcode found, try auto contrast & sharpen grayscale
    if not results:
        gray_img = ImageOps.grayscale(pil_img)
        enhanced = ImageOps.autocontrast(gray_img)
        results = zxingcpp.read_barcodes(enhanced)

    # Third pass: try slightly scaling up if image is very small (< 400px)
    if not results and max(orig_width, orig_height) < 400:
        scaled = pil_img.resize((orig_width * 2, orig_height * 2), Image.Resampling.BICUBIC)
        results = zxingcpp.read_barcodes(scaled)

    barcodes_data: List[Dict[str, Any]] = []
    annotated_img = pil_img.copy()
    draw = ImageDraw.Draw(annotated_img)

    for idx, r in enumerate(results, start=1):
        fmt_name = r.format.name
        is_2d = any(k in fmt_name.lower() for k in ["qr", "matrix", "aztec", "pdf417", "maxicode"])
        
        # Position points
        pos = r.position
        pts = [
            (pos.top_left.x, pos.top_left.y),
            (pos.top_right.x, pos.top_right.y),
            (pos.bottom_right.x, pos.bottom_right.y),
            (pos.bottom_left.x, pos.bottom_left.y)
        ]
        
        # Draw bounding polygon on annotated image
        try:
            line_color = (16, 185, 129) if is_2d else (59, 130, 246) # Green for 2D, Blue for 1D
            draw.polygon(pts, outline=line_color, width=max(3, int(min(orig_width, orig_height) / 150)))
            for pt in pts:
                r_dot = max(4, int(min(orig_width, orig_height) / 80))
                draw.ellipse([pt[0] - r_dot, pt[1] - r_dot, pt[0] + r_dot, pt[1] + r_dot], fill=line_color)
        except Exception as draw_err:
            logger.warning(f"Lỗi vẽ annotation: {draw_err}")

        parsed_meta = parse_barcode_content(r.text)

        barcodes_data.append({
            "index": idx,
            "text": r.text,
            "format": fmt_name,
            "is_2d": is_2d,
            "type_label": "2D Code" if is_2d else "1D Barcode",
            "ec_level": getattr(r, "ec_level", ""),
            "orientation": getattr(r, "orientation", 0),
            "position": {
                "top_left": [pos.top_left.x, pos.top_left.y],
                "top_right": [pos.top_right.x, pos.top_right.y],
                "bottom_right": [pos.bottom_right.x, pos.bottom_right.y],
                "bottom_left": [pos.bottom_left.x, pos.bottom_left.y]
            },
            "parsed": parsed_meta
        })

    # Prepare preview image base64
    preview_thumb = annotated_img.copy()
    preview_thumb.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    preview_thumb.save(buf, format="JPEG", quality=85)
    preview_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return {
        "success": True,
        "count": len(barcodes_data),
        "barcodes": barcodes_data,
        "image_width": orig_width,
        "image_height": orig_height,
        "annotated_image_url": f"data:image/jpeg;base64,{preview_b64}"
    }

