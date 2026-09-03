from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Float, Text
)
from sqlalchemy.orm import relationship
from app.database import Base

class RolePermission(Base):
    __tablename__ = "role_permissions"
    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False)

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    description = Column(String(255), default="")
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="role")
    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles")

class Permission(Base):
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50), default="general")
    description = Column(String(255), default="")

    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), default="")
    email = Column(String(100), default="")
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    role = relationship("Role", back_populates="users")
    policy = relationship("UserPolicy", back_populates="user", uselist=False, cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")

class UserPolicy(Base):
    """Bảng thuộc tính ABAC (Attribute-Based Access Control) cho từng người dùng"""
    __tablename__ = "user_policies"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    max_daily_downloads = Column(Integer, default=15)  # -1 = không giới hạn
    max_file_size_mb = Column(Integer, default=500)    # Dung lượng tối đa mỗi file
    can_use_ocr = Column(Boolean, default=True)
    can_use_telegram = Column(Boolean, default=True)
    daily_downloads_count = Column(Integer, default=0)
    last_download_date = Column(Date, default=date.today)

    user = relationship("User", back_populates="policy")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    username = Column(String(50), default="anonymous")
    action = Column(String(50), nullable=False)  # download, preview, delete, pin, tools, ocr
    service = Column(String(50), default="general") # scribd, youtube, facebook, direct, tools
    resource_url = Column(Text, default="")
    status = Column(String(20), default="success") # success, failed
    file_size_mb = Column(Float, default=0.0)
    ip_address = Column(String(50), default="")
    user_agent = Column(String(255), default="")
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="audit_logs")