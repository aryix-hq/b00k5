#!/usr/bin/env bash
# ==============================================================================
# LOCAL GIT RUNNER (OLLAMA HYBRID WORKER)
# ==============================================================================
# Automates Git operations (commit messages, PR drafting, branch naming) via
# local Ollama ($0 / 0 cloud token cost).
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
  echo "[local-git] Local LLM mode is switched OFF (Mode: cloud). Please run standard git commands or use cloud assistant."
  exit 2
fi

query_ollama() {
  local prompt="$1"
  python3 -c "
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
        # Clean markdown codeblocks and outer quotes
        raw = re.sub(r'^\`\`\`(?:sh|bash|git)?\n?', '', raw)
        raw = re.sub(r'\n?\`\`\`$', '', raw)
        raw = raw.strip('\"\'\` ')
        print(raw)
except Exception as e:
    print(f'Error connecting to Ollama: {e}', file=sys.stderr)
    sys.exit(1)
" "${OLLAMA_HOST}" "${MODEL}" <<< "${prompt}"
}

cmd_commit() {
  local hint="${1:-}"
  
  # Check if anything is staged; if not, stage modified tracked files
  if git diff --cached --quiet; then
    echo "[local-git] No changes staged. Staging tracked modified files..."
    git add -u
  fi

  local diff_content
  diff_content=$(git diff --cached --stat || true)
  local full_diff
  full_diff=$(git diff --cached | head -n 300 || true)

  if [[ -z "${diff_content}" ]]; then
    echo "[local-git] No changes detected to commit."
    exit 0
  fi

  echo "[local-git] Generating conventional commit message via Ollama (${MODEL})..."
  local prompt="You are an expert Git assistant following the Conventional Commits specification.
Generate a single-line conventional commit message (format: <type>(<scope>): <short description>).
Allowed types: feat, fix, docs, refactor, test, chore, perf.
${hint:+Optional User Context/Hint: ${hint}}

Diff Summary:
${diff_content}

Diff Sample:
${full_diff}

Output ONLY the single-line commit message. Do not include markdown formatting, backticks, quotes, or conversational explanations."

  local raw_output
  raw_output=$(query_ollama "${prompt}")
  local commit_msg
  commit_msg=$(echo "${raw_output}" | grep -m 1 -E '^[a-z]+(\([a-z0-9_-]+\))?:' || true)
  if [[ -z "${commit_msg}" ]]; then
    commit_msg=$(echo "${raw_output}" | head -n 1)
  fi

  if [[ -z "${commit_msg}" ]]; then
    echo "[local-git] Failed to generate commit message from Ollama."
    exit 1
  fi

  echo "[local-git] Commit message: ${commit_msg}"
  git commit -m "${commit_msg}"
}

cmd_pr() {
  local target_branch="${1:-main}"
  local commits
  commits=$(git log "${target_branch}..HEAD" --oneline || true)
  local diff_stat
  diff_stat=$(git diff "${target_branch}...HEAD" --stat || true)

  if [[ -z "${commits}" ]]; then
    echo "[local-git] No commits ahead of ${target_branch}."
    exit 0
  fi

  echo "[local-git] Drafting Pull Request description via Ollama (${MODEL})..."
  local prompt="You are an expert technical lead drafting a GitHub Pull Request description.
Target branch: ${target_branch}
Commits:
${commits}

Diff Stat:
${diff_stat}

Draft a clear PR description with:
1. ### Summary of Changes (2-3 bullet points)
2. ### Testing & Verification (how it was tested)
3. ### Impact & Invariants

Output ONLY the markdown PR description."

  query_ollama "${prompt}"
}

cmd_branch() {
  local desc="${1:-}"
  if [[ -z "${desc}" ]]; then
    echo "Usage: local-git.sh branch <feature_description>"
    exit 1
  fi

  echo "[local-git] Generating branch name via Ollama (${MODEL})..."
  local prompt="Generate a clean git branch name following the format feat/<kebab-case-slug> or fix/<kebab-case-slug> for:
${desc}

Output ONLY the raw branch name (e.g. feat/payroll-contractors). No quotes, no markdown, no spaces."

  local branch_name
  branch_name=$(query_ollama "${prompt}" | tr -d ' ' | tr '[:upper:]' '[:lower:]' | head -n 1 || true)
  echo "[local-git] Creating and switching to branch: ${branch_name}"
  git checkout -b "${branch_name}"
}

SUBCMD="${1:-help}"
shift || true

case "${SUBCMD}" in
  commit)
    cmd_commit "$@"
    ;;
  pr)
    cmd_pr "$@"
    ;;
  branch)
    cmd_branch "$@"
    ;;
  *)
    echo "Usage: local-git.sh [commit [hint] | pr [target_branch] | branch <description>]"
    ;;
esac
