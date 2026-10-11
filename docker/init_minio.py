import os
import time
import logging
from minio import Minio

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("minio_init")

host = os.getenv("MINIO_HOST", "minio")
port = os.getenv("MINIO_PORT", "9000")
user = os.getenv("MINIO_ROOT_USER", "minio_storage_admin")
password = os.getenv("MINIO_ROOT_PASSWORD", "minio_storage_secret_key_2026")
endpoint = f"{host}:{port}"

BUCKETS = [
    "b00k5-vault",
    "b00k5-receipts",
    "b00k5-statements",
    "b00k5-signed",
    "b00k5-statutory"
]

def init_buckets():
    logger.info(f"Connecting to MinIO at {endpoint}...")
    client = Minio(endpoint, access_key=user, secret_key=password, secure=False)

    for i in range(15):
        try:
            for bucket in BUCKETS:
                if not client.bucket_exists(bucket):
                    client.make_bucket(bucket)
                    logger.info(f"Created MinIO bucket: {bucket}")
                else:
                    logger.info(f"Bucket already exists: {bucket}")
            logger.info("All MinIO buckets successfully initialized!")
            return
        except Exception as e:
            logger.warning(f"MinIO connection attempt {i+1} failed: {e}. Retrying in 2 seconds...")
            time.sleep(2)

if __name__ == "__main__":
    init_buckets()
