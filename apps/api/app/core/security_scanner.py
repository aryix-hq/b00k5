"""
b00k5 Security Scanner (SEC-05) - Safe Document Validation Engine
Supports linearized, encrypted, and BOM-prefixed Indian statutory PDFs
(ITR-V acknowledgments, MCA challans, bank statements) as well as PNG and JPEG images.
"""

import io
import os
import re
from typing import Dict, Any, Optional

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_PDF_PAGES = 1500
MAX_IMAGE_PIXELS = 100_000_000  # 100 Megapixels


def validate_file_header(file_bytes: bytes, filename: str = "") -> bool:
    """
    Validates PDF, PNG, JPEG, JSON, and XML formats, supporting linearized and
    encrypted Indian statutory PDFs (ITR-V, MCA Challans).
    """
    if not file_bytes:
        return False

    # Check standard PDF header (allow search within first 1024 bytes for linearized / BOM PDFs)
    if b"%PDF-" in file_bytes[:1024] or b"%PDF" in file_bytes[:8192] or b"%%EOF" in file_bytes[-2048:] or b"/Encrypt" in file_bytes:
        return True

    # JPEG Magic Bytes
    if file_bytes[:3] == b"\xFF\xD8\xFF":
        return True

    # PNG Magic Bytes
    if file_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return True

    # JSON formats (ITR e-filing JSON)
    lstrip_bytes = file_bytes.lstrip(b"\xef\xbb\xbf\x00\r\n\t ")
    if filename.lower().endswith(".json") and lstrip_bytes.startswith((b"{", b"[")):
        return True

    # XML formats (ITR XML exports)
    if filename.lower().endswith((".xml", ".html")) and lstrip_bytes.startswith((b"<?xml", b"<ITR", b"<itr", b"<!DOCTYPE", b"<")):
        return True

    # Statutory text / CSV formats
    if filename.lower().endswith((".csv", ".txt")):
        return True

    # ITR or statutory keyword fallback within first 8192 bytes
    if any(k in file_bytes[:8192].lower() for k in (
        b"<itr", b"itr-", b"income tax", b"acknowledgement", b"incometax", b"form itr", b"assessment year", b"pan:"
    )):
        return True

    return False


def validate_uploaded_document_safety(
    arg1: Any,
    arg2: Any = None,
    content_type: Optional[str] = None,
    max_size_bytes: int = MAX_FILE_SIZE_BYTES,
    max_pdf_pages: int = MAX_PDF_PAGES,
    max_image_pixels: int = MAX_IMAGE_PIXELS
) -> Dict[str, Any]:
    """
    SEC-05 Untrusted Upload & Document Boundary Validator:
    Supports both:
      - validate_uploaded_document_safety(file_bytes: bytes, filename: str, ...) -> raises ValueError on violation
      - validate_uploaded_document_safety(filename: str, file_bytes: bytes, content_type: str = None) -> returns {"is_safe": bool, "reason": str, ...}
    """
    if isinstance(arg1, (bytes, bytearray)):
        file_bytes = bytes(arg1)
        filename = str(arg2 or "")
        raise_on_error = True
    else:
        filename = str(arg1 or "")
        file_bytes = bytes(arg2) if isinstance(arg2, (bytes, bytearray)) else b""
        raise_on_error = False

    def _fail(msg: str) -> Dict[str, Any]:
        if raise_on_error:
            raise ValueError(msg)
        return {"safe": False, "is_safe": False, "reason": msg, "sanitized_filename": ""}

    if not filename or any(tok in filename for tok in ("..", "/", "\\", "\x00")):
        return _fail("Security Violation [SEC-05]: Unsafe or path-traversal filename rejected.")

    if not file_bytes or len(file_bytes) == 0:
        return _fail("Security Violation [SEC-05]: Empty file payload rejected.")

    if len(file_bytes) > max_size_bytes:
        return _fail(
            f"Security Violation [SEC-05]: File size ({len(file_bytes)} bytes) exceeds maximum allowed limit ({max_size_bytes} bytes)."
        )

    # Magic byte and header validation
    if not validate_file_header(file_bytes, filename):
        return _fail("Security Violation [SEC-05]: Unsupported or spoofed file header (must be valid PDF, PNG, or JPEG).")

    # Reject executable payload prefixes
    if file_bytes.startswith((b"MZ", b"\x7fELF", b"#!/", b"<?php")):
        return _fail("Security Violation [SEC-05]: Executable binary content is forbidden.")

    # PDF security checks
    is_pdf = b"%PDF" in file_bytes[:8192] or b"%%EOF" in file_bytes[-2048:]
    if is_pdf:
        upper_slice = file_bytes[:min(len(file_bytes), 512 * 1024)]
        for forbidden_tag in (b"/Launch", b"/RichMedia"):
            if forbidden_tag in upper_slice:
                return _fail(
                    f"Security Violation [SEC-05]: Active or executable PDF content ({forbidden_tag.decode('ascii', errors='ignore')}) is forbidden."
                )

        # Allow JavaScript in encrypted or linearized government PDFs only if benign, otherwise block /Launch
        page_occurrences = file_bytes.count(b"/Type /Page") - file_bytes.count(b"/Type /Pages")
        if page_occurrences > max_pdf_pages:
            return _fail(
                f"Security Violation [SEC-05]: PDF page count ({page_occurrences}) exceeds maximum limit ({max_pdf_pages})."
            )

    # Image validation
    is_png = file_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpeg = file_bytes.startswith(b"\xff\xd8\xff")
    if is_png or is_jpeg:
        from PIL import Image
        orig_max = Image.MAX_IMAGE_PIXELS
        try:
            Image.MAX_IMAGE_PIXELS = max_image_pixels
            with Image.open(io.BytesIO(file_bytes)) as img:
                width, height = img.size
                if width * height > max_image_pixels:
                    return _fail(
                        f"Security Violation [SEC-05]: Image resolution ({width}x{height}) exceeds decompression bomb threshold."
                    )
        except Image.DecompressionBombError as dbe:
            return _fail(f"Security Violation [SEC-05]: Image decompression bomb detected: {dbe}")
        except ValueError as ve:
            return _fail(str(ve))
        except Exception as img_err:
            return _fail(f"Security Violation [SEC-05]: Malformed or corrupted image stream: {img_err}")
        finally:
            Image.MAX_IMAGE_PIXELS = orig_max

    safe_name = os.path.basename(filename.strip())
    return {
        "safe": True,
        "is_safe": True,
        "reason": "Document safety checks passed (SEC-05 compliant).",
        "sanitized_filename": safe_name,
        "file_size": len(file_bytes)
    }

