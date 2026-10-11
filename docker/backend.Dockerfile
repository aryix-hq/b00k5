FROM python:3.11-slim

WORKDIR /app

# Install system dependencies:
# - build-essential & libpq-dev for PostgreSQL asyncpg/psycopg2
# - poppler-utils for pdf2image PDF rendering
# - libgl1 & libglib2.0-0 for OpenCV receipt pre-processing
# - curl for container health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    postgresql-client \
    curl \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY apps/api /app/apps/api
COPY workers /app/workers
COPY packages /app/packages

ENV PYTHONPATH="/app/apps/api:/app"
ENV PYTHONUNBUFFERED=1

WORKDIR /app/apps/api

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
