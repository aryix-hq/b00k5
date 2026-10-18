#!/usr/bin/env bash
# ==============================================================================
# LOCAL CODER RUNNER (OLLAMA HYBRID WORKER)
# ==============================================================================
# Sends code generation & refactoring tasks directly to local Ollama.
# Ensures $0 / 0 Cloud Token consumption for code drafting.
# ==============================================================================
set -euo pipefail

MODEL="${OLLAMA_MODEL:-qwen2.5-coder:14b}"
OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"

PROMPT="${1:-}"
CONTEXT_FILE="${2:-}"

if [[ -z "${PROMPT}" ]]; then
  echo "Usage: local-coder.sh <prompt> [context_file]"
  exit 1
fi

PAYLOAD_PROMPT="${PROMPT}"
if [[ -n "${CONTEXT_FILE}" && -f "${CONTEXT_FILE}" ]]; then
  FILE_CONTENT=$(cat "${CONTEXT_FILE}")
  PAYLOAD_PROMPT="Context from ${CONTEXT_FILE}:
\`\`\`
${FILE_CONTENT}
\`\`\`

Instruction: ${PROMPT}
Output ONLY the replacement code or diff. No conversational preamble."
fi

# Query Ollama
python3 -c "
import urllib.request, json, sys

url = '${OLLAMA_HOST}/api/generate'
data = {
    'model': '${MODEL}',
    'prompt': '''${PAYLOAD_PROMPT}''',
    'stream': False
}
req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        print(result.get('response', ''))
except Exception as e:
    print(f'Error connecting to Ollama: {e}', file=sys.stderr)
    sys.exit(1)
"

