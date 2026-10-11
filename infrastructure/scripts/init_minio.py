#!/usr/bin/env python3
"""
MinIO Auto-initialization Script for b00k5 Phase 0.
Provisions three isolated S3 buckets:
- b00k5-statements (raw bank uploads)
- b00k5-receipts (bills, AP vouchers)
- b00k5-statutory (notices, minutes, signed PDFs)
"""

import os
import sys
import time
from minio import Minio

ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000").replace("http://", "").replace("https://", "")
ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minio_storage_admin")
SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minio_storage_secret_key_2026")

BUCKETS = [
    os.getenv("MINIO_BUCKET_STATEMENTS", "b00k5-statements"),
    os.getenv("MINIO_BUCKET_RECEIPTS", "b00k5-receipts"),
    os.getenv("MINIO_BUCKET_STATUTORY", "b00k5-statutory"),
]

def init_buckets():
    print(f"Connecting to MinIO at {ENDPOINT}...")
    client = Minio(ENDPOINT, access_key=ACCESS_KEY, secret_key=SECRET_KEY, secure=False)

    for attempt in range(15):
        try:
            for bucket in BUCKETS:
                if not client.bucket_exists(bucket):
                    client.make_bucket(bucket)
                    print(f"✓ Provisioned MinIO bucket: {bucket}")
                else:
                    print(f"✓ MinIO bucket exists: {bucket}")
            print("MinIO auto-initialization successful.")
            return True
        except Exception as e:
            print(f"Waiting for MinIO ({attempt+1}/15): {e}")
            time.sleep(1)

    print("Failed to initialize MinIO buckets within timeout.")
    return False

if __name__ == "__main__":
    success = init_buckets()
    sys.exit(0 if success else 1)
