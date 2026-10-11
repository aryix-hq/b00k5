FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY apps/api /app/apps/api
COPY workers /app/workers
COPY packages /app/packages

ENV PYTHONPATH="/app/apps/api:/app:/app/workers"
ENV PYTHONUNBUFFERED=1

WORKDIR /app

CMD ["celery", "-A", "app.core.celery_app", "worker", "-Q", "ocr_queue,compliance_queue,sync_queue", "--loglevel=info", "-c", "2"]
