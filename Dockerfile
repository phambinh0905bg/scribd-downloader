FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8000 \
    HOST=0.0.0.0

# Cài đặt ffmpeg phục vụ ghép video và convert audio MP3
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài đặt toàn bộ wheels offline (tốc độ < 1 giây, 0 byte tải từ internet)
COPY wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt && rm -rf /wheels

# Sao chép mã nguồn ứng dụng
COPY . /app/
RUN mkdir -p /app/downloads

EXPOSE 8000
VOLUME ["/app/downloads"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
