import os
import io
import sys
import time
import json
import base64
import tarfile
import requests
import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Configurations
def get_env_var(key: str, default: str = "") -> str:
    val = os.environ.get(key)
    if val:
        return val
    # Fallback to hermes .env if exists
    hermes_env = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / ".env"
    if hermes_env.exists():
        try:
            with open(hermes_env, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.strip().startswith(f"{key}="):
                        return line.strip().split("=", 1)[1].strip()
        except Exception:
            pass
    return default

PORTAINER_URL = os.environ.get("PORTAINER_URL", "http://192.168.1.250:9000")
PORTAINER_TOKEN = get_env_var("HOME_PORTAINER_TOKEN")
ENDPOINT_ID = os.environ.get("PORTAINER_ENDPOINT_ID", "3")

GH_USERNAME = os.environ.get("GH_USERNAME", "phambinh0905bg")
GH_TOKEN = get_env_var("GH_TOKEN", get_env_var("GITHUB_TOKEN"))
REGISTRY_HOST = "ghcr.io"
IMAGE_TAG = f"{REGISTRY_HOST}/{GH_USERNAME}/scribd-downloader:latest"


CONTAINER_NAME = "scribd-downloader"
HOST_PORT = "8000"

HEADERS = {
    "X-API-Key": PORTAINER_TOKEN
}

DOCKER_API_BASE = f"{PORTAINER_URL}/api/endpoints/{ENDPOINT_ID}/docker"

def log(msg, level="INFO"):
    t = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] [{level}] {msg}", flush=True)

def create_build_tar() -> bytes:
    log("📦 Đang đóng gói thư mục nguồn thành tar archive...")
    base_dir = Path(__file__).resolve().parent
    tar_stream = io.BytesIO()
    
    ignore_dirs = {".git", ".venv", "venv", "env", "__pycache__", ".idea", ".vscode", "temp_images"}
    ignore_files = {".DS_Store", "build_push_deploy.py", "deploy_remote.py", "test_inspect.py"}
    
    file_count = 0
    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        for root, dirs, files in os.walk(base_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                if file in ignore_files or file.endswith(".pyc"):
                    continue
                file_path = Path(root) / file
                arcname = file_path.relative_to(base_dir).as_posix()
                if arcname.startswith("downloads/") and arcname != "downloads/.gitkeep":
                    continue
                tar.add(str(file_path), arcname=arcname)
                file_count += 1
                
    tar_stream.seek(0)
    data = tar_stream.read()
    log(f"✅ Đã đóng gói {file_count} files ({round(len(data)/1024, 1)} KB)", "SUCCESS")
    return data

def build_docker_image(tar_bytes: bytes):
    log(f"🔨 Đang build Docker image '{IMAGE_TAG}'...")
    build_url = f"{DOCKER_API_BASE}/build?t={IMAGE_TAG}&nocache=false"
    
    headers = {
        **HEADERS,
        "Content-Type": "application/x-tar"
    }
    
    res = requests.post(build_url, headers=headers, data=tar_bytes, stream=True, timeout=(60, 1800))
    if res.status_code != 200:
        log(f"❌ Lỗi khi build image ({res.status_code}): {res.text}", "ERROR")
        sys.exit(1)
        
    for line in res.iter_lines(decode_unicode=True):
        if line:
            try:
                msg_obj = json.loads(line)
                if "stream" in msg_obj:
                    msg = msg_obj["stream"].strip()
                    if msg:
                        log(f"[Build] {msg}")
                elif "error" in msg_obj:
                    log(f"❌ [Build Error] {msg_obj['error']}", "ERROR")
                    sys.exit(1)
            except Exception:
                pass
                
    log(f"✅ Build & Tag thành công: {IMAGE_TAG}", "SUCCESS")

def push_image_to_ghcr():
    log(f"🚀 Đang push image '{IMAGE_TAG}' lên GitHub Container Registry ({REGISTRY_HOST})...")
    
    auth_config = {
        "username": GH_USERNAME,
        "password": GH_TOKEN,
        "serveraddress": REGISTRY_HOST
    }
    auth_header = base64.b64encode(json.dumps(auth_config).encode()).decode()
    
    push_url = f"{DOCKER_API_BASE}/images/{IMAGE_TAG}/push"
    headers = {
        **HEADERS,
        "X-Registry-Auth": auth_header
    }
    
    res = requests.post(push_url, headers=headers, stream=True, timeout=(60, 1800))
    if res.status_code != 200:
        log(f"❌ Lỗi push image ({res.status_code}): {res.text}", "ERROR")
        sys.exit(1)
        
    for line in res.iter_lines(decode_unicode=True):
        if line:
            try:
                msg_obj = json.loads(line)
                if "status" in msg_obj:
                    p_id = msg_obj.get("id", "")
                    p_prog = msg_obj.get("progress", "")
                    log(f"[Push] {p_id} {msg_obj['status']} {p_prog}".strip())
                elif "error" in msg_obj:
                    log(f"❌ [Push Error] {msg_obj['error']}", "ERROR")
                    sys.exit(1)
            except Exception:
                pass
                
    log(f"🎉 Push thành công image lên GHCR: https://ghcr.io/{GH_USERNAME}/scribd-downloader", "SUCCESS")

def remove_existing_container():
    log(f"🔍 Kiểm tra container cũ '{CONTAINER_NAME}'...")
    list_url = f"{DOCKER_API_BASE}/containers/json?all=1"
    res = requests.get(list_url, headers=HEADERS)
    if res.status_code == 200:
        containers = res.json()
        for c in containers:
            names = c.get("Names", [])
            if f"/{CONTAINER_NAME}" in names:
                c_id = c["Id"]
                log(f"⚠️ Dừng & xóa container cũ ({c_id[:12]})...", "WARN")
                requests.post(f"{DOCKER_API_BASE}/containers/{c_id}/stop", headers=HEADERS)
                requests.delete(f"{DOCKER_API_BASE}/containers/{c_id}?v=1&force=true", headers=HEADERS)
                log("✅ Đã xóa container cũ.", "SUCCESS")
                return

def create_and_start_container():
    log(f"🚀 Khởi tạo container '{CONTAINER_NAME}' từ image '{IMAGE_TAG}' (Port {HOST_PORT}:8000)...")
    create_url = f"{DOCKER_API_BASE}/containers/create?name={CONTAINER_NAME}"
    
    container_config = {
        "Image": IMAGE_TAG,
        "ExposedPorts": {
            "8000/tcp": {}
        },
        "Env": [
            "PORT=8000",
            "HOST=0.0.0.0",
            "CLEANUP_MINUTES=30",
            "MAX_CONCURRENT_DOWNLOADS=3",
            "DEVICE_SCALE_FACTOR=2.0"
        ],
        "HostConfig": {
            "PortBindings": {
                "8000/tcp": [
                    {
                        "HostPort": HOST_PORT
                    }
                ]
            },
            "RestartPolicy": {
                "Name": "unless-stopped"
            },
            "ShmSize": 2147483648
        }
    }
    
    headers = {
        **HEADERS,
        "Content-Type": "application/json"
    }
    
    res = requests.post(create_url, headers=headers, json=container_config)
    if res.status_code not in (200, 201):
        log(f"❌ Lỗi tạo container ({res.status_code}): {res.text}", "ERROR")
        sys.exit(1)
        
    c_data = res.json()
    c_id = c_data["Id"]
    log(f"✅ Đã tạo container ID: {c_id[:12]}", "SUCCESS")
    
    start_url = f"{DOCKER_API_BASE}/containers/{c_id}/start"
    res_start = requests.post(start_url, headers=HEADERS)
    if res_start.status_code not in (200, 204):
        log(f"❌ Lỗi khởi chạy container ({res_start.status_code}): {res_start.text}", "ERROR")
        sys.exit(1)
        
    log(f"✅ Container '{CONTAINER_NAME}' đã khởi chạy thành công từ image GHCR!", "SUCCESS")

def verify_deployment():
    log(f"🔍 Kiểm tra ứng dụng tại http://192.168.1.250:{HOST_PORT}...")
    for attempt in range(1, 8):
        time.sleep(2)
        try:
            res = requests.get(f"http://192.168.1.250:{HOST_PORT}/", timeout=5)
            if res.status_code == 200 and "Scribd Document Downloader" in res.text:
                log(f"🎉 ỨNG DỤNG ĐÃ SẴN SÀNG HOẠT ĐỘNG HOÀN HẢO TẠI CỔNG {HOST_PORT}!", "SUCCESS")
                log(f"👉 Link truy cập: http://192.168.1.250:{HOST_PORT}", "SUCCESS")
                return
        except Exception:
            pass

if __name__ == "__main__":
    print("=" * 70, flush=True)
    print("  BUILD DOCKER IMAGE -> PUSH GHCR -> DEPLOY REMOTE CONTAINER", flush=True)
    print("=" * 70 + "\n", flush=True)
    
    tar_bytes = create_build_tar()
    build_docker_image(tar_bytes)
    push_image_to_ghcr()
    remove_existing_container()
    create_and_start_container()
    verify_deployment()
    
    print("\n" + "=" * 70, flush=True)

