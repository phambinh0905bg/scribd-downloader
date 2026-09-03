import time
import json
import hmac
import hashlib
import base64
import os
import secrets
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any, Tuple
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.orm import Session
from app.config import settings

logger = logging.getLogger("auth")

def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def _b64decode(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s.encode("utf-8"))

# ==================== PASSWORD HASHING (PBKDF2-HMAC-SHA256) ====================

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=100000
    )
    return f"pbkdf2_sha256$100000${salt}${key.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = parts[2]
        expected_hex = parts[3]
        
        computed = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations=iterations
        )
        return hmac.compare_digest(computed.hex(), expected_hex)
    except Exception as e:
        logger.warning(f"Lỗi verify password: {e}")
        return False

# ==================== SESSION TOKEN (HMAC-SHA256) ====================

def create_access_token(username: str, remember: bool = True) -> str:
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
            return None
            
        payload = json.loads(_b64decode(payload_b64).decode("utf-8"))
        if payload.get("exp", 0) < int(time.time()):
            return None
            
        return payload.get("sub")
    except Exception:
        return None

def get_current_username(request: Request) -> Optional[str]:
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

# Alias for backward compatibility
get_current_user = get_current_username

def authenticate_user_db(username: str, password: str, db: Session) -> Optional[Any]:
    import app.models as models
    user = db.query(models.User).filter_by(username=username.strip()).first()
    if not user:
        # Fallback to config admin if DB has no users
        if username.strip() == settings.ADMIN_USERNAME and password == settings.ADMIN_PASSWORD:
            return True
        return None
        
    if not user.is_active:
        return None
        
    if verify_password(password, user.password_hash):
        user.last_login = datetime.utcnow()
        try:
            db.commit()
        except Exception:
            db.rollback()
        return user
    return None

def authenticate_user(username: str, password: str) -> bool:
    """Wrapper cho các route cần kiểm tra nhanh"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        user = authenticate_user_db(username, password, db)
        return user is not None
    finally:
        db.close()

# ==================== RBAC & ABAC POLICY ENFORCEMENT ====================

def get_user_with_permissions(username: str, db: Session) -> Optional[Any]:
    import app.models as models
    return db.query(models.User).filter_by(username=username).first()

def check_permission_and_abac(
    user: Any, 
    permission_code: str, 
    file_size_mb: Optional[float] = None, 
    is_ocr: bool = False
) -> Tuple[bool, str]:
    """
    Kiểm tra bảo mật 2 lớp:
    1. RBAC: Role của user có quyền 'permission_code' không?
    2. ABAC: Hạn mức ngày, dung lượng tối đa, tính năng OCR theo chính sách người dùng.
    """
    if not user:
        return False, "Yêu cầu đăng nhập."
        
    role = user.role
    if not role:
        return False, "Người dùng chưa được phân vai trò."
        
    # SuperAdmin có toàn quyền
    if role.name == "superadmin":
        return True, ""
        
    # 1. RBAC Check
    user_perm_codes = {p.code for p in role.permissions}
    if permission_code not in user_perm_codes:
        return False, f"Vai trò '{role.display_name}' không có quyền '{permission_code}'."
        
    # 2. ABAC Check
    policy = user.policy
    if policy:
        # Kiểm tra reset ngày mới
        today = date.today()
        if policy.last_download_date != today:
            policy.daily_downloads_count = 0
            policy.last_download_date = today

        # Hạn mức lượt tải trong ngày
        if policy.max_daily_downloads != -1 and policy.daily_downloads_count >= policy.max_daily_downloads:
            return False, f"Bạn đã dùng hết hạn mức ({policy.max_daily_downloads} lượt/ngày). Vui lòng quay lại vào ngày mai!"

        # Dung lượng tối đa
        if file_size_mb and policy.max_file_size_mb > 0 and file_size_mb > policy.max_file_size_mb:
            return False, f"Kích thước tệp ({file_size_mb} MB) vượt quá hạn mức tối đa của bạn ({policy.max_file_size_mb} MB)."

        # Quyền sử dụng OCR
        if is_ocr and not policy.can_use_ocr:
            return False, "Tài khoản của bạn chưa được cấp quyền sử dụng tính năng OCR."

    return True, ""

def record_download_stat(user_id: int, db: Session, action: str = "download", service: str = "general", resource_url: str = "", ip_address: str = "", file_size_mb: float = 0.0):
    import app.models as models
    try:
        policy = db.query(models.UserPolicy).filter_by(user_id=user_id).first()
        if policy:
            today = date.today()
            if policy.last_download_date != today:
                policy.daily_downloads_count = 0
                policy.last_download_date = today
            policy.daily_downloads_count += 1

        # Ghi log audit
        log = models.AuditLog(
            user_id=user_id,
            action=action,
            service=service,
            resource_url=resource_url[:500] if resource_url else "",
            status="success",
            file_size_mb=file_size_mb,
            ip_address=ip_address
        )
        db.add(log)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Lỗi ghi nhận thống kê tải: {e}")