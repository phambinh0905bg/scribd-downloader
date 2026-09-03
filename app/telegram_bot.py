import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
import requests
from app.config import settings

logger = logging.getLogger("telegram_bot")

CONFIG_PATH = settings.DOWNLOADS_DIR / "telegram_config.json"

def get_telegram_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Lỗi đọc telegram_config.json: {e}")
    return {
        "bot_token": "",
        "chat_id": "",
        "auto_send_enabled": False
    }

def save_telegram_config(bot_token: str, chat_id: str, auto_send_enabled: bool) -> Dict[str, Any]:
    cfg = {
        "bot_token": bot_token.strip(),
        "chat_id": str(chat_id).strip(),
        "auto_send_enabled": bool(auto_send_enabled)
    }
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Lỗi lưu telegram_config.json: {e}")
    return cfg

async def send_telegram_message(text: str) -> Dict[str, Any]:
    cfg = get_telegram_config()
    token = cfg.get("bot_token")
    chat_id = cfg.get("chat_id")
    if not token or not chat_id:
        return {"success": False, "error": "Chưa cấu hình Bot Token hoặc Chat ID"}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    def do_request():
        return requests.post(url, json=payload, timeout=15)

    try:
        resp = await asyncio.to_thread(do_request)
        data = resp.json()
        if data.get("ok"):
            return {"success": True}
        return {"success": False, "error": data.get("description", "Unknown error")}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def send_telegram_file(file_path: Path, caption: str = "") -> Dict[str, Any]:
    cfg = get_telegram_config()
    token = cfg.get("bot_token")
    chat_id = cfg.get("chat_id")
    if not token or not chat_id:
        return {"success": False, "error": "Chưa cấu hình Telegram Bot"}

    if not file_path.exists():
        return {"success": False, "error": "Tệp tin không tồn tại"}

    ext = file_path.suffix.lower()
    if ext in [".mp4", ".mov", ".mkv"]:
        endpoint = "sendVideo"
        file_field = "video"
    elif ext in [".mp3", ".m4a", ".wav", ".aac"]:
        endpoint = "sendAudio"
        file_field = "audio"
    else:
        endpoint = "sendDocument"
        file_field = "document"

    url = f"https://api.telegram.org/bot{token}/{endpoint}"

    def do_upload():
        with open(file_path, "rb") as f:
            files = {file_field: (file_path.name, f)}
            data = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption[:1024]
            return requests.post(url, data=data, files=files, timeout=120)

    try:
        resp = await asyncio.to_thread(do_upload)
        data = resp.json()
        if data.get("ok"):
            logger.info(f"✅ Đã gửi tệp {file_path.name} tới Telegram ({chat_id}) thành công!")
            return {"success": True}
        return {"success": False, "error": data.get("description", "Lỗi gửi file")}
    except Exception as e:
        logger.error(f"Lỗi khi gửi tệp lên Telegram: {e}")
        return {"success": False, "error": str(e)}