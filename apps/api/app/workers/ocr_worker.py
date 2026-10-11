import re
from decimal import Decimal
import numpy as np
from app.core.celery_app import celery_app
from app.services.gst_calculator import validate_gstin_checksum

GSTIN_REGEX = re.compile(r'\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b')
DATE_REGEX = re.compile(r'\b(0?[1-9]|[12][0-9]|3[01])[/-](0?[1-9]|1[012])[/-](\d{4}|\d{2})\b')
TOTAL_KEYWORD_REGEX = re.compile(
    r'(grand\s*total|total\s*amount|net\s*amount|invoice\s*total|amount\s*payable|total)',
    re.IGNORECASE
)
AMOUNT_REGEX = re.compile(r'₹?\s*([0-9]+[,\.0-9]*\.[0-9]{2})')

def preprocess_image_bytes(image_bytes: bytes):
    import cv2
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    return enhanced

def extract_indian_bill_data(image_bytes: bytes) -> dict:
    """Extract vendor, GSTIN, Date, Total, and Tax lines from receipt image."""
    try:
        from paddleocr import PaddleOCR
        ocr_engine = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
        processed_img = preprocess_image_bytes(image_bytes)
        if processed_img is None:
            return {"error": "Invalid image format"}
        result = ocr_engine.ocr(processed_img, cls=True)
    except Exception as e:
        # Fallback if paddleocr is not installed on host architecture
        return {
            "error": f"OCR Engine unavailable: {e}",
            "merchant_name": "Pending Manual Review",
            "total_amount": 0.00
        }

    lines = []
    if result and result[0]:
        for line in result[0]:
            text = line[1][0].strip()
            confidence = line[1][1]
            lines.append((text, confidence))

    full_text = " \n ".join([l[0] for l in lines])

    # 1. Extract GSTIN & Validate checksum
    gstin_match = GSTIN_REGEX.search(full_text)
    detected_gstin = None
    is_valid_gstin = False
    if gstin_match:
        cand_gstin = gstin_match.group(0)
        detected_gstin = cand_gstin
        is_valid_gstin = validate_gstin_checksum(cand_gstin)

    # 2. Extract Date
    date_match = DATE_REGEX.search(full_text)
    detected_date = date_match.group(0) if date_match else None

    # 3. Extract Grand Total
    extracted_total = Decimal("0.00")
    for idx, (text, conf) in enumerate(lines):
        if TOTAL_KEYWORD_REGEX.search(text):
            amt_match = AMOUNT_REGEX.search(text)
            if not amt_match and idx + 1 < len(lines):
                amt_match = AMOUNT_REGEX.search(lines[idx + 1][0])
            if amt_match:
                clean_num = amt_match.group(1).replace(",", "")
                try:
                    extracted_total = Decimal(clean_num)
                    break
                except Exception:
                    pass

    # 4. Merchant Name Heuristic
    detected_merchant = lines[0][0] if len(lines) > 0 else "Unknown Merchant"

    return {
        "merchant_name": detected_merchant,
        "gstin": detected_gstin,
        "is_gstin_checksum_valid": is_valid_gstin,
        "expense_date": detected_date,
        "total_amount": float(extracted_total),
        "raw_text_summary": full_text[:500]
    }

@celery_app.task(name="app.workers.ocr_worker.process_receipt_task")
def process_receipt_task(image_bytes_base64: str, expense_id: str):
    import base64
    image_bytes = base64.b64decode(image_bytes_base64)
    parsed = extract_indian_bill_data(image_bytes)
    return {"expense_id": expense_id, "data": parsed}
