import os
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

logger = logging.getLogger("database")

# Database URL: default to dedicated scribd-postgres container on home-network
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    "postgresql://scribd_admin:ScribdSecurePass2026!@scribd-postgres:5432/scribd_hub"
)

# Connect with auto-reconnect and pooling
try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )
except Exception as e:
    logger.warning(f"Lỗi khởi tạo PostgreSQL Engine ({e}). Fallback sang SQLite nội bộ...")
    sqlite_path = settings.DATA_DIR / "scribd_hub_fallback.db"
    engine = create_engine(f"sqlite:///{sqlite_path}", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Khởi tạo cấu trúc bảng và nạp dữ liệu mẫu ban đầu (Roles, Permissions, SuperAdmin)."""
    import app.models as models
    from app.auth import hash_password
    from datetime import date
    
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Đã tạo bảng cơ sở dữ liệu thành công!")
    except Exception as e:
        logger.error(f"Lỗi tạo bảng database: {e}")
        return

    db = SessionLocal()
    try:
        # 1. Khởi tạo danh mục Permissions
        DEFAULT_PERMS = [
            ("download:scribd", "Tải tài liệu Scribd", "download", "Cho phép tải tài liệu từ Scribd"),
            ("download:youtube", "Tải video YouTube", "download", "Cho phép tải video và âm thanh YouTube"),
            ("download:social", "Tải Mạng Xã Hội", "download", "Cho phép tải video Facebook, TikTok, Instagram"),
            ("download:direct", "Tải Remote URL", "download", "Cho phép kéo tệp tin từ URL trực tiếp"),
            ("feature:ocr", "Nhận diện chữ OCR", "feature", "Cho phép tạo PDF có lớp text tìm kiếm qua OCR"),
            ("feature:tools", "Bộ công cụ tệp", "feature", "Cho phép nén, ghép PDF và tách audio MP3"),
            ("feature:telegram", "Gửi file Telegram", "feature", "Cho phép cấu hình và gửi tệp về Telegram"),
            ("files:view_own", "Xem tệp của mình", "files", "Xem danh sách và tải về các tệp của mình"),
            ("files:view_all", "Xem tất cả tệp", "files", "Xem và tải toàn bộ tệp trong hệ thống"),
            ("files:delete_all", "Xóa tệp hệ thống", "files", "Xóa bất kỳ tệp nào khỏi máy chủ"),
            ("admin:users_manage", "Quản lý người dùng", "admin", "Thêm, sửa, xóa, khóa tài khoản người dùng"),
            ("admin:roles_manage", "Quản lý phân quyền", "admin", "Quản lý vai trò và ma trận quyền hạn"),
            ("admin:audit_logs", "Xem nhật ký tải", "admin", "Xem lịch sử tải và địa chỉ IP truy cập"),
        ]

        perm_map = {}
        for code, name, cat, desc in DEFAULT_PERMS:
            p = db.query(models.Permission).filter_by(code=code).first()
            if not p:
                p = models.Permission(code=code, name=name, category=cat, description=desc)
                db.add(p)
                db.flush()
            perm_map[code] = p

        # 2. Khởi tạo các Roles mặc định
        ROLES_CONFIG = [
            ("superadmin", "Quản Trị Viên Tối Cao", "Toàn quyền quản trị hệ thống, người dùng và phân quyền", True, list(perm_map.keys())),
            ("vip", "Thành Viên VIP", "Không giới hạn lượt tải, đầy đủ tính năng OCR, công cụ tệp và Telegram", True, [
                "download:scribd", "download:youtube", "download:social", "download:direct",
                "feature:ocr", "feature:tools", "feature:telegram", "files:view_own"
            ]),
            ("member", "Thành Viên Chuẩn", "Đầy đủ các nguồn tải cơ bản và bộ công cụ tệp", True, [
                "download:scribd", "download:youtube", "download:social",
                "feature:tools", "files:view_own"
            ]),
            ("guest", "Khách Vãng Lai", "Hạn mức tải thấp, xem trước và tải tài liệu cơ bản", True, [
                "download:scribd", "files:view_own"
            ])
        ]

        role_map = {}
        for r_name, r_disp, r_desc, is_sys, perm_codes in ROLES_CONFIG:
            r = db.query(models.Role).filter_by(name=r_name).first()
            if not r:
                r = models.Role(name=r_name, display_name=r_disp, description=r_desc, is_system=is_sys)
                db.add(r)
                db.flush()
                for pcode in perm_codes:
                    if pcode in perm_map:
                        rp = models.RolePermission(role_id=r.id, permission_id=perm_map[pcode].id)
                        db.add(rp)
            role_map[r_name] = r

        # 3. Tạo tài khoản SuperAdmin ban đầu
        admin_user = db.query(models.User).filter_by(username="admin").first()
        if not admin_user:
            admin_user = models.User(
                username="admin",
                password_hash=hash_password("admin123456"),
                full_name="Quản Trị Viên Hệ Thống",
                email="admin@binh.name.vn",
                role_id=role_map["superadmin"].id,
                is_active=True
            )
            db.add(admin_user)
            db.flush()

            # ABAC policy cho admin: không giới hạn (-1)
            policy = models.UserPolicy(
                user_id=admin_user.id,
                max_daily_downloads=-1,
                max_file_size_mb=10000,
                can_use_ocr=True,
                can_use_telegram=True,
                daily_downloads_count=0,
                last_download_date=date.today()
            )
            db.add(policy)
            logger.info("Đã tạo tài khoản SuperAdmin 'admin' mặc định!")

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Lỗi khởi tạo dữ liệu mẫu: {e}")
    finally:
        db.close()