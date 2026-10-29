#!/usr/bin/env bash
# ==============================================================================
# LOCAL COMMAND RUNNER (OLLAMA HYBRID WORKER)
# ==============================================================================
# Translates natural language requests into exact terminal/shell commands using
# local Ollama ($0 / 0 cloud tokens) and optionally executes them.
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
import urllib.request, json, sys, re, os, subprocess

prompt = sys.stdin.read()
url = sys.argv[1] + '/api/generate'
model = sys.argv[2]
script_dir = sys.argv[3]

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
        
        # Log token usage
        prompt_tokens = result.get('prompt_eval_count', 0)
        eval_tokens = result.get('eval_count', 0)
        candidates = [
            os.path.join(script_dir, 'record-tokens.py'),
            os.path.expanduser('~/.local/bin/record-tokens.py')
        ]
        record_script = next((c for c in candidates if os.path.exists(c)), None)
        if record_script:
            subprocess.run([
                'python3', record_script,
                '--record',
                '--tool', 'local-cmd',
                '--model', model,
                '--prompt-tokens', str(prompt_tokens),
                '--eval-tokens', str(eval_tokens)
            ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Strip markdown fences
        raw = re.sub(r'^\`\`\`(?:sh|bash|zsh)?\n?', '', raw)
        raw = re.sub(r'\n?\`\`\`$', '', raw)
        raw = raw.strip('\"\'\` ')
        print(raw)
except Exception as e:
    err_str = str(e)
    print(f'[local-cmd] Error connecting to Ollama at {url}: {err_str}', file=sys.stderr)
    if 'Operation not permitted' in err_str or 'Errno 1' in err_str:
        print('[local-cmd] NOTE: Antigravity terminal sandbox blocks loopback network (127.0.0.1:11434). Please re-run command with BypassSandbox: true.', file=sys.stderr)
    sys.exit(1)
" "${OLLAMA_HOST}" "${MODEL}" "${SCRIPT_DIR}" <<< "${SYSTEM_PROMPT}")

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
