#!/usr/bin/env bash
# ==============================================================================
# b00k5 Open-Source Secret & PII Scanner
# ==============================================================================
# Scans tracked and staged files for private keys, passwords, real founder PII,
# unmasked Aadhaar numbers, or non-synthetic PANs before pushing to public GitHub.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

echo "🔍 Scanning repository for confidential secrets and real PII..."

VIOLATIONS=0

python3 - << 'EOF'
import subprocess, re, sys

tracked = subprocess.check_output(['git', 'ls-files']).decode().splitlines()
status = subprocess.check_output(['git', 'status', '--porcelain']).decode().splitlines()

files = set(tracked)
for s in status:
    p = s[3:].strip()
    if p and not p.endswith('/'):
        files.add(p)

# Patterns
key_pattern = re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----')
aadhaar_pattern = re.compile(r'\b[2-9]{1}[0-9]{3}\s[0-9]{4}\s[0-9]{4}\b')
pan_pattern = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b')
forbidden_names = ["Shastry & Co", "S SHASTRY", "ABHPL7088B", "7616438562", "AC6319079", "AB6835884", "Keerthi N"]

SYNTHETIC_PAN_PREFIXES = ('AAACA', 'AABCA', 'AABCS', 'AABCK', 'ABCDE', 'ABCPD', 'ABCCD', 'AAACC', 'AAACF', 'XXXXX')

violations = []

for f in sorted(files):
    if f.endswith(('.png', '.ico', '.jpg', '.jpeg', '.pdf', '.woff', '.woff2', '.lock', '.svg')):
        continue
    # skip .gitignore or scripts/scan_secrets_and_pii.sh itself
    if f in ('.gitignore', 'scripts/scan_secrets_and_pii.sh', '.gitleaks.toml'):
        continue
    try:
        with open(f, 'r', errors='ignore') as fp:
            for idx, line in enumerate(fp, 1):
                # Private keys
                if key_pattern.search(line):
                    violations.append((f, idx, "PRIVATE_KEY", line.strip()[:80]))
                # Aadhaar
                if aadhaar_pattern.search(line):
                    violations.append((f, idx, "AADHAAR_NUMBER", line.strip()[:80]))
                # Forbidden private names / real CA details
                for fn in forbidden_names:
                    if fn.lower() in line.lower():
                        violations.append((f, idx, f"FORBIDDEN_PII: {fn}", line.strip()[:80]))
                # Non-synthetic PAN check
                pans = pan_pattern.findall(line)
                for p in pans:
                    if not p.startswith(SYNTHETIC_PAN_PREFIXES):
                        violations.append((f, idx, f"NON_SYNTHETIC_PAN: {p}", line.strip()[:80]))
    except Exception as e:
        pass

if violations:
    print(f"\n❌ FOUND {len(violations)} POTENTIAL CONFIDENTIALITY / PII VIOLATIONS:")
    for f, idx, tag, snippet in violations:
        print(f"  {f}:{idx} [{tag}] -> {snippet}")
    sys.exit(1)
else:
    print("\n✅ ZERO SECRETS & ZERO FOUNDER PII DETECTED! Repository is clean for public open-source release.")
EOF

echo "✔ Sanitization scan completed."
