#!/bin/sh
set -e

echo "=== b00k5 MinIO Bucket Auto-Provisioner ==="

MINIO_HOST="${MINIO_HOST:-b00k5_minio}"
MINIO_PORT="${MINIO_PORT:-9000}"
MINIO_USER="${MINIO_ROOT_USER:-minio_storage_admin}"
MINIO_PASSWORD="${MINIO_ROOT_PASSWORD:-minio_storage_secret_key_2026}"

echo "Waiting for MinIO at http://${MINIO_HOST}:${MINIO_PORT}..."
until curl -s -f "http://${MINIO_HOST}:${MINIO_PORT}/minio/health/live" > /dev/null 2>&1; do
    echo "MinIO not ready yet, sleeping 2s..."
    sleep 2
done

echo "MinIO is healthy. Configuring alias..."
mc alias set local "http://${MINIO_HOST}:${MINIO_PORT}" "$MINIO_USER" "$MINIO_PASSWORD"

echo "Creating isolated b00k5 S3 storage buckets with public-read disabled..."
BUCKETS="b00k5-vault b00k5-receipts b00k5-statements b00k5-signed b00k5-statutory"

for bucket in $BUCKETS; do
    if ! mc ls "local/${bucket}" > /dev/null 2>&1; then
        echo "Creating bucket: ${bucket}..."
        mc mb "local/${bucket}"
    else
        echo "Bucket already exists: ${bucket}"
    fi
    # Strictly disable public-read
    mc anonymous set none "local/${bucket}" || true
done

echo "=== MinIO Provisioning Complete ==="
exit 0
