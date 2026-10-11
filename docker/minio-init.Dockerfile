FROM python:3.11-alpine

WORKDIR /app
RUN pip install --no-cache-dir minio

COPY docker/init_minio.py /app/init_minio.py

ENTRYPOINT ["python", "/app/init_minio.py"]
