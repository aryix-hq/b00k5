import io
import pytest
from unittest.mock import MagicMock, patch
from app.services.s3_mirror_client import S3RemoteMirrorClient, clean_endpoint


def test_clean_endpoint():
    assert clean_endpoint("https://abc.r2.cloudflarestorage.com/") == "abc.r2.cloudflarestorage.com"
    assert clean_endpoint("http://s3.ap-south-1.amazonaws.com") == "s3.ap-south-1.amazonaws.com"
    assert clean_endpoint("s3.amazonaws.com") == "s3.amazonaws.com"
    assert clean_endpoint("") == ""


def test_s3_mirror_client_initialization():
    client = S3RemoteMirrorClient(
        endpoint="https://myaccount.r2.cloudflarestorage.com",
        access_key="test_access_key",
        secret_key="test_secret_key",
        bucket_name="test-vault",
        region="auto",
        root_prefix="b00k5_ARYIX"
    )
    assert client.endpoint == "myaccount.r2.cloudflarestorage.com"
    assert client.bucket_name == "test-vault"
    assert client.root_prefix == "b00k5_ARYIX"


def test_s3_mirror_test_connection_missing_creds():
    client = S3RemoteMirrorClient(
        endpoint="",
        access_key="",
        secret_key="",
        bucket_name=""
    )
    res = client.test_connection()
    assert res["success"] is False
    assert res["connected"] is False
    assert "Missing required S3 credentials" in res["error"]


def test_s3_mirror_test_connection_mock_success():
    client = S3RemoteMirrorClient(
        endpoint="https://account.r2.cloudflarestorage.com",
        access_key="test_key",
        secret_key="test_secret",
        bucket_name="my-bucket"
    )

    mock_minio = MagicMock()
    mock_minio.bucket_exists.return_value = True
    mock_minio.put_object.return_value = MagicMock()
    mock_minio.remove_object.return_value = None

    with patch.object(S3RemoteMirrorClient, "client", new=mock_minio):
        res = client.test_connection()
        assert res["success"] is True
        assert res["connected"] is True
        assert res["provider"] == "Cloudflare R2"
        assert res["bucket_name"] == "my-bucket"
        assert "latency_ms" in res
        mock_minio.put_object.assert_called_once()
        mock_minio.remove_object.assert_called_once()


def test_s3_mirror_upload_file_mock():
    client = S3RemoteMirrorClient(
        endpoint="https://account.r2.cloudflarestorage.com",
        access_key="test_key",
        secret_key="test_secret",
        bucket_name="my-bucket",
        root_prefix="b00k5_TEST"
    )

    mock_minio = MagicMock()
    mock_minio.put_object.return_value = MagicMock()

    with patch.object(S3RemoteMirrorClient, "client", new=mock_minio):
        payload = b"%PDF-1.4 Mock Statutory Document"
        res = client.upload_file(
            relative_path="Corporate Legal/COI.pdf",
            file_bytes=payload,
            content_type="application/pdf"
        )
        assert res["bucket"] == "my-bucket"
        assert res["object_key"] == "b00k5_TEST/Corporate Legal/COI.pdf"
        assert res["s3_uri"] == "s3://my-bucket/b00k5_TEST/Corporate Legal/COI.pdf"
        assert res["size_bytes"] == len(payload)
        assert "sha256" in res
        mock_minio.put_object.assert_called_once()

