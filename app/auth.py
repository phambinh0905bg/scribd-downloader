import time
import json
import hmac
import hashlib
import base64
import logging
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from app.config import settings

logger = logging.getLogger("auth")

def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def _b64decode(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s.encode("utf-8"))

def create_access_token(username: str, remember: bool = True) -> str:
    """
    Tạo token ký HMAC-SHA256 chứa username và thời gian hết hạn (exp).
    """
    duration_days = settings.SESSION_EXPIRE_DAYS if remember else 1
    exp = int(time.time()) + (duration_days * 86400)
    
    payload = {
        "sub": username,
        "exp": exp,
        "iat": int(time.time())
    }
    
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode("utf-8")
    payload_b64 = _b64encode(payload_bytes)
    
    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256
    ).digest()
    sig_b64 = _b64encode(signature)
    
    return f"{payload_b64}.{sig_b64}"

def verify_access_token(token: str) -> Optional[str]:
    """
    Xác minh token HMAC-SHA256. Trả về username nếu hợp lệ, None nếu không hợp lệ hoặc hết hạn.
    """
    if not token or "." not in token:
        return None
        
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256
        ).digest()
        
        actual_sig = _b64decode(sig_b64)
        
        if not hmac.compare_digest(expected_sig, actual_sig):
            logger.warning("Token signature mismatch")
            return None
            
        payload = json.loads(_b64decode(payload_b64).decode("utf-8"))
        
        if payload.get("exp", 0) < int(time.time()):
            logger.info("Token expired")
            return None
            
        return payload.get("sub")
    except Exception as e:
        logger.warning(f"Lỗi kiểm tra token: {e}")
        return None

def authenticate_user(username: str, password: str) -> bool:
    """
    Kiểm tra tên đăng nhập và mật khẩu an toàn theo thời gian hằng số.
    """
    valid_user = hmac.compare_digest(username.strip(), settings.ADMIN_USERNAME)
    valid_pass = hmac.compare_digest(password, settings.ADMIN_PASSWORD)
    return valid_user and valid_pass

def get_current_user(request: Request) -> Optional[str]:
    """
    Lấy thông tin người dùng từ Cookie 'auth_token' hoặc Header Authorization Bearer.
    """
    if not settings.AUTH_ENABLED:
        return settings.ADMIN_USERNAME
        
    token = request.cookies.get(settings.COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            
    if not token:
        return None
        
    return verify_access_token(token)