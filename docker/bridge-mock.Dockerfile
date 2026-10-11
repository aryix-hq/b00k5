FROM python:3.11-slim

WORKDIR /app

# Install SoftHSM2, OpenSC, OpenSSL, and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    softhsm2 \
    opensc \
    gnutls-bin \
    openssl \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Symlink SoftHSM2 dynamic library to candidate PKCS#11 driver paths
RUN SOFTHSM_PATH=$(find /usr/lib -name "libsofthsm2.so" | head -n 1) && \
    mkdir -p /usr/local/lib && \
    ln -s "$SOFTHSM_PATH" /usr/lib/libespki.so && \
    ln -s "$SOFTHSM_PATH" /usr/local/lib/libespki.so

# Initialize SoftHSM2 token store & import test certificate
RUN mkdir -p /var/lib/softhsm/tokens && \
    softhsm2-util --init-token --slot 0 --label "HYP 2003 Token" --pin 123456 --so-pin 12345678 && \
    openssl req -x509 -newkey rsa:2048 -keyout /tmp/dsc_key.pem -out /tmp/dsc_cert.pem -days 365 -nodes \
      -subj "/C=IN/ST=Karnataka/L=Bengaluru/O=Acme Technologies Private Limited/OU=Director/CN=Vikram Sharma" && \
    openssl pkcs12 -export -out /tmp/dsc.p12 -inkey /tmp/dsc_key.pem -in /tmp/dsc_cert.pem -passout pass:123456 && \
    pkcs11-tool --module /usr/lib/libespki.so --login --pin 123456 --write-object /tmp/dsc_cert.pem --type cert --id 01 --label "Director DSC" 2>/dev/null || true

COPY bridge/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY bridge ./bridge

ENV B00K5_DEV_DSC_MOCK=true
ENV PYTHONUNBUFFERED=1

EXPOSE 28045

CMD ["uvicorn", "bridge.signer_service:app", "--host", "0.0.0.0", "--port", "28045"]
