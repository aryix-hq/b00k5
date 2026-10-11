"""
b00k5 HYP 2003 Hardware Bridge Daemon
Executes locally on 127.0.0.1:28045.
Interacts with HyperPKI HYP 2003 USB tokens via standard PKCS#11 native drivers.
"""

import os
import platform
import logging
from typing import Optional, List
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("b00k5_bridge")

app = FastAPI(
    title="b00k5 HYP 2003 Hardware Bridge",
    description="Local loopback bridge communicating with PKCS#11 USB Crypto tokens for MCA & GST compliance",
    version="1.0.0"
)

# Enforce strict origin checking to prevent malicious web tabs from reaching localhost signer
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

def get_candidate_driver_paths() -> List[str]:
    """Detect OS and return potential HYP 2003 dynamic driver locations."""
    system = platform.system()
    if system == "Windows":
        return [
            r"C:\Windows\System32\eps2003csp11.dll",
            r"C:\Program Files\HyperPKI\eps2003csp11.dll"
        ]
    elif system == "Linux":
        return [
            "/usr/lib/libespki.so",
            "/usr/lib/libshuttle_p11.so",
            "/usr/local/lib/libespki.so"
        ]
    elif system == "Darwin":
        return [
            "/usr/local/lib/libespki.dylib",
            "/Library/HyperPKI/libespki.dylib",
            "/opt/homebrew/lib/libespki.dylib"
        ]
    return []

def get_installed_driver_path() -> Optional[str]:
    for path in get_candidate_driver_paths():
        if os.path.exists(path):
            return path
    return None

class SignRequest(BaseModel):
    pin: str
    document_sha256_hex: str
    token_label: Optional[str] = None

class StatusResponse(BaseModel):
    bridge_status: str
    platform: str
    driver_found: bool
    driver_path: Optional[str]
    token_detected: bool
    token_label: Optional[str] = None

@app.get("/status", response_model=StatusResponse)
def get_bridge_status():
    driver_path = get_installed_driver_path()
    token_detected = False
    token_label = None

    if driver_path:
        try:
            import pkcs11
            lib = pkcs11.lib(driver_path)
            slots = lib.get_slots(token_present=True)
            if slots:
                token_detected = True
                token_label = slots[0].get_token().label
        except Exception as e:
            logger.warning(f"Error enumerating slots: {e}")

    return {
        "bridge_status": "online",
        "platform": platform.system(),
        "driver_found": driver_path is not None,
        "driver_path": driver_path,
        "token_detected": token_detected,
        "token_label": token_label
    }

@app.post("/sign-hash")
def sign_hash_with_token(request: SignRequest):
    driver_path = get_installed_driver_path()
    
    # Dev / Simulation mode if requested via environment or when hardware is absent
    allow_simulation = os.environ.get("B00K5_DEV_DSC_MOCK", "false").lower() == "true"
    if not driver_path:
        if allow_simulation:
            import hashlib
            from cryptography.hazmat.primitives.asymmetric import rsa, padding
            from cryptography.hazmat.primitives import hashes
            # In test/dev mode, generate self-contained dummy RSA signature
            priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            digest = bytes.fromhex(request.document_sha256_hex)
            sig = priv.sign(digest, padding.PKCS1v15(), hashes.SHA256())
            return {
                "status": "success",
                "simulation": True,
                "signature_hex": sig.hex(),
                "certificate_der_hex": "308201...",
                "token_label": "DevMock HYP 2003 Token"
            }
        raise HTTPException(
            status_code=500,
            detail=f"HYP 2003 PKCS#11 driver not found on {platform.system()}. Please install token middleware."
        )

    try:
        import pkcs11
        from pkcs11 import Mechanism, KeyType
    except ImportError:
        raise HTTPException(status_code=500, detail="python-pkcs11 module is not installed on bridge environment.")

    lib = pkcs11.lib(driver_path)
    slots = lib.get_slots(token_present=True)
    if not slots:
        raise HTTPException(status_code=404, detail="No HYP 2003 USB token detected. Please insert USB crypto dongle.")

    token = slots[0].get_token()

    try:
        with token.open(user_pin=request.pin) as session:
            priv_keys = list(session.get_objects({
                pkcs11.Attribute.CLASS: pkcs11.ObjectClass.PRIVATE_KEY,
                pkcs11.Attribute.KEY_TYPE: KeyType.RSA
            }))

            if not priv_keys:
                raise HTTPException(status_code=400, detail="No RSA private signing key found on token.")

            signing_key = priv_keys[0]

            certs = list(session.get_objects({
                pkcs11.Attribute.CLASS: pkcs11.ObjectClass.CERTIFICATE
            }))

            x509_cert = certs[0] if certs else None
            cert_der = x509_cert[pkcs11.Attribute.VALUE] if x509_cert else None

            digest_bytes = bytes.fromhex(request.document_sha256_hex)
            raw_signature = signing_key.sign(
                digest_bytes,
                mechanism=Mechanism.SHA256_RSA_PKCS
            )

            return {
                "status": "success",
                "simulation": False,
                "signature_hex": raw_signature.hex(),
                "certificate_der_hex": cert_der.hex() if cert_der else None,
                "token_label": token.label
            }

    except pkcs11.exceptions.PinIncorrect:
        raise HTTPException(status_code=401, detail="Invalid DSC Token PIN. Please check and retry carefully.")
    except pkcs11.exceptions.PinLocked:
        raise HTTPException(status_code=423, detail="DSC Token is LOCKED due to excessive incorrect PIN attempts.")
    except Exception as e:
        logger.error(f"Hardware crypto error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cryptographic operation failed: {str(e)}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket client connected to hardware bridge.")
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            if action == "ping":
                await websocket.send_json({"event": "pong", "status": "ready"})
            elif action == "sign":
                pin = data.get("pin")
                hash_hex = data.get("document_sha256_hex")
                try:
                    res = sign_hash_with_token(SignRequest(pin=pin, document_sha256_hex=hash_hex))
                    await websocket.send_json({"event": "signed", "payload": res})
                except HTTPException as he:
                    await websocket.send_json({"event": "error", "code": he.status_code, "detail": he.detail})
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=28045)
