# b00k5 Hardware Token (HYP 2003) Localhost Bridge

This lightweight daemon runs locally on the director/founder's physical workstation at `127.0.0.1:28045`.

## Why is this bridge needed?
Web browsers strictly forbid websites from directly accessing raw USB Smart Card devices due to OS PC/SC driver locks and sandbox policies. 
The `b00k5-bridge` allows the Next.js web application to request digital signatures from the physical HyperPKI HYP 2003 USB token via standard PKCS#11 cryptographic drivers without ever leaking the private key outside the token hardware.

## Supported Platforms & Drivers
- **Windows**: `C:\Windows\System32\eps2003csp11.dll`
- **Linux**: `/usr/lib/libespki.so` or `/usr/lib/libshuttle_p11.so`
- **macOS**: `/usr/local/lib/libespki.dylib` or `/Library/HyperPKI/libespki.dylib`

## Quick Start
```bash
cd bridge
pip install -r requirements.txt
bash run_bridge.sh
```
Daemon listens on `http://127.0.0.1:28045` and WebSocket `ws://127.0.0.1:28045/ws`.
