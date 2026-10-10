FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8000 \
    HOST=0.0.0.0

# Cài đặt ffmpeg và Tesseract OCR (Tiếng Việt & Tiếng Anh)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    tesseract-ocr \
    tesseract-ocr-vie \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài đặt dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Sao chép mã nguồn ứng dụng
COPY . /app/
RUN mkdir -p /app/downloads && \
    ( [ -f /usr/local/lib/python3.12/dist-packages/playwright/driver/node ] && ln -sf /usr/local/lib/python3.12/dist-packages/playwright/driver/node /usr/local/bin/node || true )


EXPOSE 8000
VOLUME ["/app/downloads"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
