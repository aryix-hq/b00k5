#!/usr/bin/env python3
"""
b00k5 - Google Drive OAuth 2.0 Authenticator
Enables personal @gmail.com accounts to upload documents to Google Drive
by generating an OAuth 2.0 Refresh Token and storing it for the active tenant.
"""

import sys
import json
import urllib.parse
import urllib.request
import webbrowser
import http.server
import socketserver
import subprocess

REDIRECT_URI = "http://localhost:8089"
SCOPES = "https://www.googleapis.com/auth/drive"

def main():
    print("=" * 65)
    print("   b00k5 Sovereign Financial OS - Google Drive OAuth Setup")
    print("=" * 65)
    print("\nFor personal @gmail.com accounts, Google requires OAuth 2.0 so files")
    print("are stored under your personal 15GB storage quota (bypassing the 0-byte")
    print("quota limit enforced on Service Accounts).\n")

    client_id = input("Enter your Google OAuth Client ID: ").strip()
    client_secret = input("Enter your Google OAuth Client Secret: ").strip()

    if not client_id or not client_secret:
        print("[ERROR] Client ID and Client Secret are required.")
        sys.exit(1)

    auth_params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent"
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(auth_params)

    print("\n[STEP 1] Opening your browser to authorize b00k5 with Google Drive...")
    print(f"URL: {auth_url}\n")
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    auth_code = None

    class OAuthHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            if "code" in qs:
                auth_code = qs["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Authentication successful!</h1><p>You can close this tab and return to the terminal.</p>")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Failed to capture authorization code.")

        def log_message(self, format, *args):
            return

    print(f"[STEP 2] Waiting for authorization callback on {REDIRECT_URI}...")
    with socketserver.TCPServer(("localhost", 8089), OAuthHandler) as httpd:
        httpd.handle_request()

    if not auth_code:
        print("[ERROR] Failed to obtain authorization code.")
        sys.exit(1)

    print("\n[STEP 3] Exchanging authorization code for OAuth Refresh Token...")
    token_url = "https://oauth2.googleapis.com/token"
    token_data = urllib.parse.urlencode({
        "code": auth_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }).encode("utf-8")

    req = urllib.request.Request(token_url, data=token_data, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            token_resp = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[ERROR] Token exchange failed: {e}")
        sys.exit(1)

    refresh_token = token_resp.get("refresh_token")
    access_token = token_resp.get("access_token")

    if not refresh_token:
        print("[WARNING] No refresh token returned. (Ensure 'prompt=consent' is used or revoke previous access to get a new refresh token).")

    print("[SUCCESS] OAuth 2.0 Credentials successfully obtained!")
    print(f"  Access Token: {access_token[:15]}...")
    print(f"  Refresh Token: {refresh_token[:15]}...\n")

    # Save to production postgres
    print("[STEP 4] Updating ARYIX tenant in production database...")
    sql_payload = json.dumps({
        "oauth2_client_id": client_id,
        "oauth2_client_secret": client_secret,
        "oauth2_refresh_token": refresh_token,
        "oauth2_token": access_token,
        "auth_type": "oauth2",
        "status": "connected",
        "connected": True
    })

    cmd = [
        "docker", "exec", "b00k5_postgres", "psql", "-U", "b00k5_admin", "-d", "b00k5_db", "-c",
        f"""
        UPDATE tenants 
        SET statutory_profile = jsonb_set(
            jsonb_set(
                jsonb_set(
                    jsonb_set(
                        statutory_profile::jsonb, 
                        '{{gdrive_config,oauth2_client_id}}', '"{client_id}"'::jsonb
                    ),
                    '{{gdrive_config,oauth2_client_secret}}', '"{client_secret}"'::jsonb
                ),
                '{{gdrive_config,oauth2_refresh_token}}', '"{refresh_token}"'::jsonb
            ),
            '{{gdrive_config,auth_type}}', '"oauth2"'::jsonb
        )
        WHERE id = '1890eb49-b7b7-46b8-a922-cd32d094e8f7';
        """
    ]
    try:
        subprocess.run(cmd, check=True)
        print("[SUCCESS] Production database updated with OAuth 2.0 credentials!")
        print("You can now trigger the sync sweep in the UI or run a database backup—all documents will upload under your personal storage quota!")
    except Exception as e:
        print(f"[ERROR] Failed to update database: {e}")

if __name__ == "__main__":
    main()

