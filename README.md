# Scribd Document Downloader Web App (Docker)

Ứng dụng web tải tài liệu Scribd sang định dạng PDF chất lượng cao, kèm giao diện theo dõi tiến trình trực quan theo thời gian thực (Server-Sent Events) và cơ chế tự động dọn dẹp file sau khi hết hạn.

---

## 🌟 Tính Năng Nổi Bật

1. **Chất Lượng Cao & Sắc Nét (High-DPI)**:
   - Sử dụng Playwright Chromium Engine mô phỏng hiển thị trung thực.
   - Tự động gỡ bỏ lớp làm mờ (`blur`), pop-up bản quyền và banner quảng cáo.
   - Ghép ảnh trang thành file PDF chuẩn xác, rõ nét từng câu chữ bằng `img2pdf`.

2. **Theo Dõi Tiến Trình Trực Quan Thời Gian Thực**:
   - Thanh tiến trình phần trăm (%) sống động.
   - Stepper trực quan 5 giai đoạn: *Kết nối -> Phân tích -> Render & Gỡ mờ -> Đóng gói PDF -> Hoàn tất*.
   - Hộp console nhật ký trực tiếp (Live Log Console) ghi nhận chi tiết trạng thái từng trang.

3. **Cơ Chế Tự Động Dọn Dẹp (Auto-Cleanup)**:
   - Background worker tự động quét và xóa sạch các file PDF cùng dữ liệu tạm sau thời gian cấu hình (mặc định **30 phút**).
   - Tự động giải phóng dung lượng ổ cứng, có đồng hồ đếm ngược trực tiếp trên giao diện người dùng.

4. **Tùy Chọn Khoảng Trang Linh Hoạt**:
   - Tải toàn bộ tài liệu hoặc chọn tải một phần trang (ví dụ: `1-10`, `3,5,8-12`).

5. **Đóng Gói Docker Hoàn Chỉnh**:
   - Chạy dễ dàng chỉ với 1 lệnh `docker compose up -d`.
   - Tích hợp sẵn bộ font chữ quốc tế (tiếng Việt, CJK, Unicode) chống lỗi hiển thị.

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Với Docker

### Cách 1: Chạy bằng Docker Compose (Khuyên dùng)

1. **Clone hoặc tải thư mục mã nguồn về máy:**
   ```bash
   cd acestream
   ```

2. **Khởi chạy container:**
   ```bash
   docker compose up -d --build
   ```

3. **Truy cập ứng dụng:**
   - Mở trình duyệt và truy cập: **`http://localhost:8000`**

4. **Dừng container khi không sử dụng:**
   ```bash
   docker compose down
   ```

---

### Cách 2: Chạy trực tiếp bằng Docker CLI

```bash
# Build image
docker build -t scribd-downloader .

# Chạy container
docker run -d \
  -p 8000:8000 \
  --name scribd-downloader-app \
  --shm-size=2g \
  -v $(pwd)/downloads:/app/downloads \
  -e CLEANUP_MINUTES=30 \
  scribd-downloader
```

---

## ⚙️ Cấu Hình Tùy Chỉnh (Biến Môi Trường)

Bạn có thể chỉnh sửa các thông số trong file `.env` hoặc trong `docker-compose.yml`:

| Biến môi trường | Mặc định | Mô tả |
| :--- | :--- | :--- |
| `PORT` | `8000` | Cổng dịch vụ web bên ngoài |
| `CLEANUP_MINUTES` | `30` | Thời gian tự động xóa file PDF sau khi tạo (tính theo phút) |
| `CLEANUP_INTERVAL_SECONDS`| `60` | Tần suất worker chạy kiểm tra dọn dẹp file (giây) |
| `MAX_CONCURRENT_DOWNLOADS` | `3` | Số lượng tác vụ tải xử lý đồng thời |
| `DEVICE_SCALE_FACTOR` | `2.0` | Hệ số DPI khi render trang (1.5 - 2.0 cho độ nét HD) |

---

## 📖 Hướng Dẫn Sử Dụng

1. Sao chép liên kết tài liệu Scribd bất kỳ (ví dụ: `https://www.scribd.com/document/123456789/Ten-Tai-Lieu` hoặc `https://www.scribd.com/doc/123456789/...`).
2. Dán vào ô nhập URL trên trang web (bấm nút **Dán URL**).
3. *(Tùy chọn)* Mở **Tùy chọn nâng cao** nếu bạn chỉ muốn tải một số trang nhất định (ví dụ: `1-5`).
4. Nhấn nút **Bắt Đầu Tải PDF**.
5. Quan sát thanh tiến trình và nhật ký thời gian thực.
6. Khi hoàn tất, nhấn **Tải Về Máy (PDF)** để lưu file về máy tính. Đồng hồ đếm ngược sẽ thông báo thời gian còn lại trước khi file tự động bị xóa khỏi server.

---

## 📂 Cấu Trúc Thư Mục Dự Án

```
acestream/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI Application & REST/SSE Endpoints
│   ├── config.py                # Cấu hình hệ thống & biến môi trường
│   ├── downloader.py            # Playwright Scraping Engine & Bộ đóng gói PDF
│   ├── cleanup.py               # Worker tự động dọn dẹp file quá hạn
│   ├── static/
│   │   ├── style.css            # Custom CSS & Glassmorphism UI
│   │   └── app.js               # Logic Frontend, SSE streaming, Countdown timer
│   └── templates/
│       └── index.html           # Giao diện người dùng Web UI
├── downloads/                   # Thư mục lưu trữ file PDF tạm thời
├── Dockerfile                   # Dockerfile với Playwright Chromium & Fonts
├── docker-compose.yml           # Docker Compose cấu hình sẵn
├── requirements.txt             # Thư viện Python
├── .dockerignore
├── .env.example
└── README.md
```

---

## ⚖️ Tuyên Bố Miễn Trừ Trách Nhiệm (Disclaimer)

Dự án này được phát triển cho mục đích học tập, nghiên cứu kỹ thuật trình duyệt không đầu (Headless Browser) và lưu trữ tài liệu cá nhân mà bạn có quyền truy cập hợp pháp. Vui lòng tôn trọng Điều khoản dịch vụ của Scribd và bản quyền của các tác giả.

