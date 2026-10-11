#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "Starting b00k5 HYP 2003 Hardware Token Bridge on 127.0.0.1:28045..."
python3 signer_service.py
