#!/usr/bin/env bash
# ==============================================================================
# LOCAL CODER RUNNER (OLLAMA HYBRID WORKER)
# ==============================================================================
# Sends code generation & refactoring tasks directly to local Ollama.
# Ensures $0 / 0 Cloud Token consumption for code drafting.
# ==============================================================================
set -euo pipefail

# Resolve canonical script directory even if invoked through symlinks
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
MODEL="${OLLAMA_MODEL:-qwen2.5-coder:14b}"
OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"

# Check execution mode (local vs cloud)
MODE="${AI_AGENTS_MODE:-}"
if [[ -z "${MODE}" ]]; then
  if [[ -f ".agents/mode" ]]; then
    MODE=$(cat ".agents/mode" | tr -d '[:space:]')
  elif [[ -f "${HOME}/.gemini/config/ai-agents-mode" ]]; then
    MODE=$(cat "${HOME}/.gemini/config/ai-agents-mode" | tr -d '[:space:]')
  else
    MODE="local"
  fi
fi

if [[ "${MODE}" == "cloud" ]]; then
  echo "[local-coder] Local LLM mode is switched OFF (Mode: cloud). Orchestrator should execute directly via cloud model."
  exit 2
fi

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
import urllib.request, json, sys, os, subprocess

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
        
        # Log token usage
        prompt_tokens = result.get('prompt_eval_count', 0)
        eval_tokens = result.get('eval_count', 0)
        candidates = [
            os.path.join('${SCRIPT_DIR}', 'record-tokens.py'),
            os.path.expanduser('~/.local/bin/record-tokens.py')
        ]
        record_script = next((c for c in candidates if os.path.exists(c)), None)
        if record_script:
            subprocess.run([
                'python3', record_script,
                '--record',
                '--tool', 'local-coder',
                '--model', '${MODEL}',
                '--prompt-tokens', str(prompt_tokens),
                '--eval-tokens', str(eval_tokens)
            ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
except Exception as e:
    err_str = str(e)
    print(f'[local-coder] Error connecting to Ollama at {url}: {err_str}', file=sys.stderr)
    if 'Operation not permitted' in err_str or 'Errno 1' in err_str:
        print('[local-coder] NOTE: Antigravity terminal sandbox blocks loopback network (127.0.0.1:11434). Please re-run command with BypassSandbox: true.', file=sys.stderr)
    sys.exit(1)
"
