import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Information
    APP_NAME: str = "Media & Doc Hub"
    APP_VERSION: str = "2.2.1"
    
    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Storage Settings (Mapped to /disk1/data/downloads on Host)
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DOWNLOADS_DIR: Path = BASE_DIR / "downloads"
    TEMP_DIR: Path = DOWNLOADS_DIR / "temp"
    DATA_DIR: Path = BASE_DIR / "data"
    
    # Auto-cleanup Settings (in minutes - 300 minutes = 5 hours)
    CLEANUP_MINUTES: int = 300
    CLEANUP_INTERVAL_SECONDS: int = 60
    
    # Security & Authentication Settings
    AUTH_ENABLED: bool = True
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123456"
    SECRET_KEY: str = "mediadochub-secret-key-super-secure-change-in-prod-2026"
    SESSION_EXPIRE_DAYS: int = 7
    COOKIE_NAME: str = "auth_token"
    
    # Downloader Performance & Quality
    MAX_CONCURRENT_DOWNLOADS: int = 4
    BROWSER_TIMEOUT_MS: int = 60000
    PAGE_WAIT_TIMEOUT_MS: int = 15000
    DEVICE_SCALE_FACTOR: float = 2.0  # 2.0 = High DPI (crisp text & images)
    
    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
