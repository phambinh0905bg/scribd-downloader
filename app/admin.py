from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from datetime import datetime, date

from app.database import get_db
from app.auth import get_current_username, hash_password
import app.models as models

router = APIRouter(prefix="/api/admin", tags=["admin"])

def get_current_admin(request: Request, db: Session = Depends(get_db)):
    username = get_current_username(request)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Yêu cầu đăng nhập.")
    user = db.query(models.User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Người dùng không tồn tại.")
    if user.role.name != "superadmin":
        user_perms = {p.code for p in user.role.permissions}
        if "admin:users_manage" not in user_perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập trang quản trị.")
    return user

# ==================== SCHEMAS ====================

class UserCreateRequest(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = ""
    email: Optional[str] = ""
    role_id: int
    max_daily_downloads: Optional[int] = 15
    max_file_size_mb: Optional[int] = 500
    can_use_ocr: Optional[bool] = True
    can_use_telegram: Optional[bool] = True

class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role_id: Optional[int] = None
    password: Optional[str] = None
    max_daily_downloads: Optional[int] = None
    max_file_size_mb: Optional[int] = None
    can_use_ocr: Optional[bool] = None
    can_use_telegram: Optional[bool] = None

class RolePermissionsUpdateRequest(BaseModel):
    permission_ids: List[int]

# ==================== ENDPOINTS ====================

@router.get("/me")
async def get_my_profile(request: Request, db: Session = Depends(get_db)):
    """Trả về thông tin người dùng hiện tại, vai trò, danh sách quyền và hạn mức ABAC."""
    username = get_current_username(request)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập.")
        
    user = db.query(models.User).filter_by(username=username).first()
    if not user:
        # Fallback cho tài khoản local admin
        return {
            "id": 1,
            "username": username,
            "full_name": "Quản Trị Viên",
            "role": "superadmin",
            "role_display": "Quản Trị Viên Tối Cao",
            "is_admin": True,
            "permissions": ["*"],
            "quota": {
                "max_daily": -1,
                "used_today": 0,
                "remaining": -1,
                "max_file_size_mb": 10000,
                "can_ocr": True,
                "can_telegram": True
            }
        }

    role = user.role
    policy = user.policy
    permissions = [p.code for p in role.permissions] if role else []
    is_admin = role.name == "superadmin" if role else False

    used = policy.daily_downloads_count if policy else 0
    max_d = policy.max_daily_downloads if policy else 15
    remaining = -1 if max_d == -1 else max(0, max_d - used)

    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "role": role.name if role else "guest",
        "role_display": role.display_name if role else "Khách",
        "is_admin": is_admin,
        "permissions": permissions,
        "quota": {
            "max_daily": max_d,
            "used_today": used,
            "remaining": remaining,
            "max_file_size_mb": policy.max_file_size_mb if policy else 500,
            "can_ocr": policy.can_use_ocr if policy else False,
            "can_telegram": policy.can_use_telegram if policy else False
        }
    }

@router.get("/users")
async def list_users(admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Liệt kê toàn bộ người dùng kèm vai trò và hạn mức ABAC."""
    users = db.query(models.User).order_by(models.User.id.asc()).all()
    res = []
    for u in users:
        policy = u.policy
        res.append({
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "email": u.email,
            "is_active": u.is_active,
            "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "",
            "last_login": u.last_login.strftime("%Y-%m-%d %H:%M") if u.last_login else "Chưa đăng nhập",
            "role": {
                "id": u.role.id,
                "name": u.role.name,
                "display_name": u.role.display_name
            } if u.role else None,
            "policy": {
                "max_daily_downloads": policy.max_daily_downloads if policy else 15,
                "max_file_size_mb": policy.max_file_size_mb if policy else 500,
                "can_use_ocr": policy.can_use_ocr if policy else False,
                "can_use_telegram": policy.can_use_telegram if policy else False,
                "daily_downloads_count": policy.daily_downloads_count if policy else 0
            } if policy else None
        })
    return {"status": "success", "users": res}

@router.post("/users")
async def create_user(req: UserCreateRequest, admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Thêm người dùng mới và khởi tạo chính sách ABAC."""
    if db.query(models.User).filter_by(username=req.username.strip()).first():
        raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại.")
        
    role = db.query(models.Role).filter_by(id=req.role_id).first()
    if not role:
        raise HTTPException(status_code=400, detail="Vai trò không hợp lệ.")

    new_user = models.User(
        username=req.username.strip(),
        password_hash=hash_password(req.password),
        full_name=req.full_name.strip() if req.full_name else "",
        email=req.email.strip() if req.email else "",
        role_id=role.id,
        is_active=True
    )
    db.add(new_user)
    db.flush()

    new_policy = models.UserPolicy(
        user_id=new_user.id,
        max_daily_downloads=req.max_daily_downloads if req.max_daily_downloads is not None else 15,
        max_file_size_mb=req.max_file_size_mb if req.max_file_size_mb is not None else 500,
        can_use_ocr=bool(req.can_use_ocr),
        can_use_telegram=bool(req.can_use_telegram),
        daily_downloads_count=0,
        last_download_date=date.today()
    )
    db.add(new_policy)
    db.commit()

    return {"status": "success", "message": f"Đã tạo người dùng '{new_user.username}' thành công", "user_id": new_user.id}

@router.put("/users/{user_id}")
async def update_user(user_id: int, req: UserUpdateRequest, admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Cập nhật thông tin, mật khẩu, vai trò và hạn mức ABAC của người dùng."""
    user = db.query(models.User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")

    if req.full_name is not None:
        user.full_name = req.full_name.strip()
    if req.email is not None:
        user.email = req.email.strip()
    if req.role_id is not None:
        role = db.query(models.Role).filter_by(id=req.role_id).first()
        if role:
            user.role_id = role.id
    if req.password:
        user.password_hash = hash_password(req.password)

    # Cập nhật ABAC policy
    policy = user.policy
    if not policy:
        policy = models.UserPolicy(user_id=user.id)
        db.add(policy)

    if req.max_daily_downloads is not None:
        policy.max_daily_downloads = req.max_daily_downloads
    if req.max_file_size_mb is not None:
        policy.max_file_size_mb = req.max_file_size_mb
    if req.can_use_ocr is not None:
        policy.can_use_ocr = req.can_use_ocr
    if req.can_use_telegram is not None:
        policy.can_use_telegram = req.can_use_telegram

    db.commit()
    return {"status": "success", "message": f"Đã cập nhật thông tin người dùng '{user.username}'"}

@router.post("/users/{user_id}/toggle-active")
async def toggle_user_active(user_id: int, admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Khóa hoặc kích hoạt lại người dùng."""
    user = db.query(models.User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    if user.username == "admin":
        raise HTTPException(status_code=400, detail="Không thể khóa tài khoản SuperAdmin gốc.")

    user.is_active = not user.is_active
    db.commit()
    state_str = "kích hoạt" if user.is_active else "khóa"
    return {"status": "success", "message": f"Đã {state_str} tài khoản '{user.username}'", "is_active": user.is_active}

@router.delete("/users/{user_id}")
async def delete_user(user_id: int, admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Xóa tài khoản người dùng."""
    user = db.query(models.User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    if user.username == "admin":
        raise HTTPException(status_code=400, detail="Không thể xóa tài khoản SuperAdmin gốc.")

    db.delete(user)
    db.commit()
    return {"status": "success", "message": f"Đã xóa người dùng '{user.username}'"}

@router.get("/roles")
async def list_roles(admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Lấy danh sách Roles kèm ma trận Permissions."""
    roles = db.query(models.Role).all()
    perms = db.query(models.Permission).order_by(models.Permission.category.asc()).all()

    roles_data = []
    for r in roles:
        r_perms = [p.id for p in r.permissions]
        roles_data.append({
            "id": r.id,
            "name": r.name,
            "display_name": r.display_name,
            "description": r.description,
            "is_system": r.is_system,
            "permission_ids": r_perms
        })

    perms_data = [
        {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "category": p.category,
            "description": p.description
        } for p in perms
    ]

    return {"status": "success", "roles": roles_data, "permissions": perms_data}

@router.post("/roles/{role_id}/permissions")
async def update_role_permissions(role_id: int, req: RolePermissionsUpdateRequest, admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Cập nhật ma trận quyền hạn cho Role."""
    role = db.query(models.Role).filter_by(id=role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Không tìm thấy vai trò.")

    # Xóa các liên kết cũ
    db.query(models.RolePermission).filter_by(role_id=role.id).delete()
    for pid in req.permission_ids:
        rp = models.RolePermission(role_id=role.id, permission_id=pid)
        db.add(rp)

    db.commit()
    return {"status": "success", "message": f"Đã cập nhật phân quyền cho vai trò '{role.display_name}'"}

@router.get("/audit-logs")
async def list_audit_logs(admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Lấy danh sách nhật ký tải tệp và hoạt động gần nhất."""
    logs = db.query(models.AuditLog).order_by(models.AuditLog.id.desc()).limit(100).all()
    res = []
    for l in logs:
        u_name = l.user.username if l.user else (l.username or "Anonymous")
        res.append({
            "id": l.id,
            "username": u_name,
            "action": l.action,
            "service": l.service,
            "resource_url": l.resource_url,
            "status": l.status,
            "file_size_mb": l.file_size_mb,
            "ip_address": l.ip_address,
            "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else ""
        })
    return {"status": "success", "logs": res}