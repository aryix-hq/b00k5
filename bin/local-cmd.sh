#!/usr/bin/env bash
# ==============================================================================
# LOCAL COMMAND RUNNER (OLLAMA HYBRID WORKER)
# ==============================================================================
# Translates natural language requests into exact terminal/shell commands using
# local Ollama ($0 / 0 cloud tokens) and optionally executes them.
# ==============================================================================
set -euo pipefail

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
  echo "[local-cmd] Local LLM mode is switched OFF (Mode: cloud). Please execute shell commands directly in your terminal or via cloud assistant."
  exit 2
fi

EXECUTE=false
if [[ "${1:-}" == "--exec" || "${1:-}" == "-e" ]]; then
  EXECUTE=true
  shift
fi

PROMPT="$*"
if [[ -z "${PROMPT}" ]]; then
  echo "Usage: local-cmd.sh [--exec] <natural-language-shell-task>"
  echo "Example: local-cmd.sh 'run pytest on tests/unit with 4 workers'"
  echo "Example: local-cmd.sh --exec 'find files modified in last 2 hours in src/'"
  exit 1
fi

SYSTEM_PROMPT="You are an expert macOS / zsh shell engineer.
Generate ONLY the exact one-line shell command to accomplish the user request.
Invariants:
- Output NO markdown codeblocks (\`\`\`sh or \`\`\`).
- Output NO quotes wrapping the command.
- Output NO conversational text, explanations, or warnings.
- Output raw, directly executable shell syntax.

User Request: ${PROMPT}"

CMD=$(python3 -c "
import urllib.request, json, sys, re

prompt = sys.stdin.read()
url = sys.argv[1] + '/api/generate'
model = sys.argv[2]

data = {
    'model': model,
    'prompt': prompt,
    'stream': False
}
req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        raw = result.get('response', '').strip()
        # Strip markdown fences
        raw = re.sub(r'^\`\`\`(?:sh|bash|zsh)?\n?', '', raw)
        raw = re.sub(r'\n?\`\`\`$', '', raw)
        raw = raw.strip('\"\'\` ')
        print(raw)
except Exception as e:
    print(f'Error connecting to Ollama: {e}', file=sys.stderr)
    sys.exit(1)
" "${OLLAMA_HOST}" "${MODEL}" <<< "${SYSTEM_PROMPT}")

if [[ -z "${CMD}" ]]; then
  echo "[local-cmd] Failed to generate command from Ollama."
  exit 1
fi

if [[ "${EXECUTE}" == "true" ]]; then
  echo -e "\033[1;34m[local-cmd:executing]\033[0m ${CMD}"
  eval "${CMD}"
else
  echo "${CMD}"
fi
