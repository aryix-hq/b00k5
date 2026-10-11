const BRIDGE_URL = process.env.NEXT_PUBLIC_BRIDGE_URL || 'http://127.0.0.1:28045';

export interface BridgeStatus {
  bridge_status: string;
  platform: string;
  driver_found: boolean;
  driver_path: string | null;
  token_detected: boolean;
  token_label: string | null;
}

export async function checkBridgeStatus(): Promise<BridgeStatus> {
  const url = BRIDGE_URL.replace('ws://', 'http://').replace('wss://', 'https://');
  try {
    const res = await fetch(`${url}/status`, { method: 'GET' });
    if (!res.ok) throw new Error('Bridge offline');
    return await res.json();
  } catch (err) {
    return {
      bridge_status: 'offline',
      platform: 'unknown',
      driver_found: false,
      driver_path: null,
      token_detected: false,
      token_label: null,
    };
  }
}

export async function signHashViaBridge(pin: string, document_sha256_hex: string) {
  const url = BRIDGE_URL.replace('ws://', 'http://').replace('wss://', 'https://');
  const res = await fetch(`${url}/sign-hash`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pin, document_sha256_hex }),
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Hardware DSC signing failed');
  }

  return await res.json();
}
