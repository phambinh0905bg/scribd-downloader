import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Information
    APP_NAME: str = "Scribd Document Downloader"
    APP_VERSION: str = "1.0.0"
    APP_DEBUG: bool = False

    
    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Storage Settings
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DOWNLOADS_DIR: Path = BASE_DIR / "downloads"
    
    # Auto-cleanup Settings (in minutes)
    CLEANUP_MINUTES: int = 30
    CLEANUP_INTERVAL_SECONDS: int = 60
    
    # Downloader Performance & Quality
    MAX_CONCURRENT_DOWNLOADS: int = 3
    BROWSER_TIMEOUT_MS: int = 60000
    PAGE_WAIT_TIMEOUT_MS: int = 15000
    DEVICE_SCALE_FACTOR: float = 2.0  # 2.0 = High DPI (crisp text & images)
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Ensure downloads directory exists
settings.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
