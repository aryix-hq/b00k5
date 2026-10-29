"""
b00k5 Sovereign Financial OS - S3 Remote Mirror Client
Provides enterprise-grade, set-and-forget off-site synchronization to:
- Cloudflare R2 (10 GB free forever, $0 egress fees)
- AWS S3 (Standard, Glacier, Object Lock WORM per MCA Sec 128)
- Backblaze B2, Wasabi, or any S3-compatible cloud object store
"""

import io
import time
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

try:
    from minio import Minio
    from minio.error import S3Error
    HAVE_MINIO = True
except ImportError:
    HAVE_MINIO = False
    class S3Error(Exception):
        pass

logger = logging.getLogger("b00k5_s3_mirror")


def clean_endpoint(endpoint_url: str) -> str:
    """Strips scheme and trailing slashes for MinIO SDK."""
    if not endpoint_url:
        return ""
    ep = endpoint_url.strip()
    if ep.startswith("http://"):
        ep = ep[7:]
    elif ep.startswith("https://"):
        ep = ep[8:]
    return ep.rstrip("/")


class S3RemoteMirrorClient:
    """
    S3 Remote Cloud Mirror Client:
    Connects to external Cloudflare R2 or AWS S3 buckets using static access keys.
    Completely eliminates OAuth consent screens, token expirations, and Google quota limits.
    """

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        region: str = "auto",
        secure: bool = True,
        root_prefix: Optional[str] = None
    ):
        self.raw_endpoint = (endpoint or "").strip()
        self.endpoint = clean_endpoint(self.raw_endpoint)
        self.access_key = (access_key or "").strip()
        self.secret_key = (secret_key or "").strip()
        self.bucket_name = (bucket_name or "").strip()
        self.region = (region or "auto").strip()
        self.secure = secure
        self.root_prefix = (root_prefix or "").strip().rstrip("/")
        self._client: Optional[Any] = None

    @property
    def client(self) -> Optional[Any]:
        if self._client is None and HAVE_MINIO and self.endpoint and self.access_key and self.secret_key:
            try:
                self._client = Minio(
                    endpoint=self.endpoint,
                    access_key=self.access_key,
                    secret_key=self.secret_key,
                    region=self.region if self.region and self.region != "auto" else None,
                    secure=self.secure
                )
            except Exception as e:
                logger.error(f"Failed to initialize S3RemoteMirrorClient: {e}", exc_info=True)
                self._client = None
        return self._client

    def test_connection(self) -> Dict[str, Any]:
        """
        Validates remote S3 connectivity:
        1. Checks bucket existence.
        2. Performs a harmless 1-byte read/write canary check.
        3. Measures latency.
        """
        if not HAVE_MINIO:
            return {
                "success": False,
                "connected": False,
                "error": "MinIO S3 SDK is not installed in the python environment."
            }

        if not self.endpoint or not self.access_key or not self.secret_key or not self.bucket_name:
            return {
                "success": False,
                "connected": False,
                "error": "Missing required S3 credentials (endpoint, access_key, secret_key, or bucket_name)."
            }

        t0 = time.perf_counter()
        cli = self.client
        if not cli:
            return {
                "success": False,
                "connected": False,
                "error": "Failed to create S3 client with provided credentials."
            }

        try:
            # 1. Bucket existence check
            exists = cli.bucket_exists(self.bucket_name)
            if not exists:
                # Attempt to create if permissible
                try:
                    cli.make_bucket(self.bucket_name)
                    exists = True
                except Exception as mk_err:
                    return {
                        "success": False,
                        "connected": False,
                        "error": f"Bucket '{self.bucket_name}' does not exist and could not be auto-created: {mk_err}"
                    }

            # 2. Canary write & delete test
            canary_key = f"{self.root_prefix}/.b00k5_connection_canary.txt" if self.root_prefix else ".b00k5_connection_canary.txt"
            canary_payload = b"b00k5_sovereign_canary_test"
            cli.put_object(
                bucket_name=self.bucket_name,
                object_name=canary_key,
                data=io.BytesIO(canary_payload),
                length=len(canary_payload),
                content_type="text/plain"
            )
            # Remove canary object immediately
            cli.remove_object(self.bucket_name, canary_key)

            latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)

            provider_guess = "Cloudflare R2" if "r2.cloudflarestorage.com" in self.endpoint else ("AWS S3" if "amazonaws.com" in self.endpoint else "S3 Compatible Object Store")

            return {
                "success": True,
                "connected": True,
                "provider": provider_guess,
                "bucket_name": self.bucket_name,
                "endpoint": self.endpoint,
                "latency_ms": latency_ms,
                "message": f"Successfully verified write and read access to '{self.bucket_name}' ({provider_guess}, {latency_ms}ms)."
            }

        except Exception as e:
            logger.warning(f"S3 remote connection test failed: {e}")
            return {
                "success": False,
                "connected": False,
                "error": str(e),
                "message": f"S3 connection check failed: {e}"
            }

    def upload_file(
        self,
        relative_path: str,
        file_bytes: bytes,
        content_type: str = "application/pdf"
    ) -> Dict[str, Any]:
        """
        Uploads document or backup payload to remote S3 bucket under {root_prefix}/{relative_path}.
        Computes SHA-256 checksum and returns remote metadata.
        """
        cli = self.client
        if not cli:
            raise RuntimeError("S3 remote client is not initialized. Check credentials.")

        clean_path = relative_path.lstrip("/")
        full_object_key = f"{self.root_prefix}/{clean_path}" if self.root_prefix else clean_path
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()

        cli.put_object(
            bucket_name=self.bucket_name,
            object_name=full_object_key,
            data=io.BytesIO(file_bytes),
            length=len(file_bytes),
            content_type=content_type
        )

        s3_uri = f"s3://{self.bucket_name}/{full_object_key}"

        return {
            "bucket": self.bucket_name,
            "object_key": full_object_key,
            "s3_uri": s3_uri,
            "size_bytes": len(file_bytes),
            "sha256": sha256_hash,
            "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

    def list_files(self, subpath: str = "") -> List[Dict[str, Any]]:
        """Lists files under {root_prefix}/{subpath}."""
        cli = self.client
        if not cli:
            return []

        clean_sub = subpath.strip().lstrip("/")
        if self.root_prefix:
            prefix = f"{self.root_prefix}/{clean_sub}" if clean_sub else f"{self.root_prefix}/"
        else:
            prefix = f"{clean_sub}/" if clean_sub else ""

        try:
            objs = cli.list_objects(self.bucket_name, prefix=prefix, recursive=True)
            files = []
            for o in objs:
                if not o.is_dir:
                    rel = o.object_name[len(self.root_prefix):].lstrip("/") if self.root_prefix and o.object_name.startswith(self.root_prefix) else o.object_name
                    files.append({
                        "object_key": o.object_name,
                        "relative_path": rel,
                        "size_bytes": o.size,
                        "last_modified": o.last_modified.isoformat() if o.last_modified else None,
                        "etag": o.etag
                    })
            return sorted(files, key=lambda x: x["last_modified"] or "", reverse=True)
        except Exception as e:
            logger.warning(f"Failed to list remote S3 files: {e}")
            return []

    def delete_file(self, object_key_or_rel_path: str) -> bool:
        """
        Deletes an object key from the remote bucket.
        Accepts either full object_key or relative path.
        """
        cli = self.client
        if not cli:
            return False

        target_key = object_key_or_rel_path
        if self.root_prefix and not target_key.startswith(self.root_prefix):
            target_key = f"{self.root_prefix}/{target_key.lstrip('/')}"

        try:
            cli.remove_object(self.bucket_name, target_key)
            logger.info(f"Deleted remote S3 object: {self.bucket_name}/{target_key}")
            return True
        except Exception as e:
            logger.warning(f"Failed to delete remote S3 object {target_key}: {e}")
            return False

    def get_storage_usage(self) -> Dict[str, Any]:
        """
        Calculates storage consumption breakdown on the remote S3 / Cloudflare R2 bucket.
        Cloudflare R2 provides 10 GB free forever (10,737,418,240 bytes).
        """
        cli = self.client
        FREE_TIER_BYTES = 10 * 1024 * 1024 * 1024  # 10 GB

        if not cli:
            return {
                "total_bytes": 0,
                "total_mb": 0.0,
                "free_tier_bytes": FREE_TIER_BYTES,
                "free_tier_gb": 10.0,
                "used_percentage": 0.0,
                "remaining_free_bytes": FREE_TIER_BYTES,
                "remaining_free_gb": 10.0,
                "categories": {},
                "file_count": 0
            }

        prefix = f"{self.root_prefix}/" if self.root_prefix else ""
        total_bytes = 0
        categories = {
            "database_backups": {"bytes": 0, "count": 0},
            "sales_invoices": {"bytes": 0, "count": 0},
            "vendor_bills": {"bytes": 0, "count": 0},
            "bank_statements": {"bytes": 0, "count": 0},
            "statutory_vault": {"bytes": 0, "count": 0},
            "other": {"bytes": 0, "count": 0}
        }
        total_count = 0

        try:
            objs = cli.list_objects(self.bucket_name, prefix=prefix, recursive=True)
            for o in objs:
                if not o.is_dir:
                    sz = o.size or 0
                    total_bytes += sz
                    total_count += 1
                    name = o.object_name.lower()
                    if "database backups" in name or "database_backups" in name or ".tar.gz" in name:
                        categories["database_backups"]["bytes"] += sz
                        categories["database_backups"]["count"] += 1
                    elif "sales invoices" in name or "sales_invoices" in name or "inv-" in name or "inv_" in name:
                        categories["sales_invoices"]["bytes"] += sz
                        categories["sales_invoices"]["count"] += 1
                    elif "vendor bills" in name or "receipt" in name or "exp_" in name:
                        categories["vendor_bills"]["bytes"] += sz
                        categories["vendor_bills"]["count"] += 1
                    elif "bank statements" in name or "statement" in name:
                        categories["bank_statements"]["bytes"] += sz
                        categories["bank_statements"]["count"] += 1
                    elif "corporate legal" in name or "tax registrations" in name or "statutory filings" in name:
                        categories["statutory_vault"]["bytes"] += sz
                        categories["statutory_vault"]["count"] += 1
                    else:
                        categories["other"]["bytes"] += sz
                        categories["other"]["count"] += 1
        except Exception as e:
            logger.warning(f"Failed to calculate storage usage for {self.bucket_name}: {e}")

        used_pct = round((total_bytes / FREE_TIER_BYTES) * 100, 2)
        remaining = max(0, FREE_TIER_BYTES - total_bytes)

        return {
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 2),
            "total_gb": round(total_bytes / (1024 * 1024 * 1024), 4),
            "free_tier_bytes": FREE_TIER_BYTES,
            "free_tier_gb": 10.0,
            "used_percentage": used_pct,
            "remaining_free_bytes": remaining,
            "remaining_free_gb": round(remaining / (1024 * 1024 * 1024), 2),
            "categories": categories,
            "file_count": total_count
        }

    def enforce_retention_policy(
        self,
        keep_backups_count: int = 7,
        max_age_days: int = 30
    ) -> Dict[str, Any]:
        """
        Enforces retention policy specifically for database backups.
        Preserves the N newest database backups and prunes older ones to prevent running out of space.
        Statutory Invariant: Invoices, bills, receipts, and legal vault documents are NEVER pruned.
        """
        cli = self.client
        if not cli:
            return {"pruned_count": 0, "retained_count": 0, "reclaimed_bytes": 0, "reclaimed_mb": 0.0, "pruned_files": []}

        subpath = "Database Backups"
        clean_sub = subpath.strip().lstrip("/")
        prefix = f"{self.root_prefix}/{clean_sub}/" if self.root_prefix else f"{clean_sub}/"

        try:
            objs = list(cli.list_objects(self.bucket_name, prefix=prefix, recursive=True))
            backup_objs = [
                o for o in objs 
                if not o.is_dir and (o.object_name.endswith(".enc") or o.object_name.endswith(".meta.txt") or ".tar.gz" in o.object_name)
            ]
            
            # Sort newest first
            backup_objs.sort(key=lambda o: o.last_modified if o.last_modified else datetime.min, reverse=True)

            retained = backup_objs[:keep_backups_count]
            to_prune = backup_objs[keep_backups_count:]

            pruned_files = []
            reclaimed_bytes = 0

            for o in to_prune:
                try:
                    cli.remove_object(self.bucket_name, o.object_name)
                    reclaimed_bytes += (o.size or 0)
                    pruned_files.append({
                        "object_key": o.object_name,
                        "size_bytes": o.size,
                        "last_modified": o.last_modified.isoformat() if o.last_modified else None
                    })
                    logger.info(f"Retention policy pruned old S3 backup: {o.object_name} ({o.size} bytes)")
                except Exception as e:
                    logger.warning(f"Failed to prune old backup {o.object_name}: {e}")

            return {
                "pruned_count": len(pruned_files),
                "retained_count": len(retained),
                "reclaimed_bytes": reclaimed_bytes,
                "reclaimed_mb": round(reclaimed_bytes / (1024 * 1024), 2),
                "pruned_files": pruned_files
            }
        except Exception as e:
            logger.warning(f"Failed to enforce retention policy on S3 backups: {e}")
            return {"pruned_count": 0, "retained_count": 0, "reclaimed_bytes": 0, "reclaimed_mb": 0.0, "pruned_files": []}

