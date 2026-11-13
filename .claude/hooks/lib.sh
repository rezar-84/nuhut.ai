# Shared by the ai-sdlc POSIX shims; sourced, never run directly.
# All hook evaluation, JSON parsing/formatting, symlink resolution, and secret/PII
# pattern matching live in `.ai-sdlc/bin/hooks.py` (Python 3 stdlib, zero `jq` or
# GNU sed required).

hook_find_python() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi
  return 1
}

hook_find_engine() {
  _hfe_dir=$1
  for _cand in \
    "${CLAUDE_PROJECT_DIR:-}/.ai-sdlc/bin/hooks.py" \
    "${GEMINI_PROJECT_DIR:-}/.ai-sdlc/bin/hooks.py" \
    "${CURSOR_PROJECT_DIR:-}/.ai-sdlc/bin/hooks.py" \
    "$_hfe_dir/../../.ai-sdlc/bin/hooks.py" \
    "$_hfe_dir/../bin/hooks.py" \
    "$_hfe_dir/../../optional/runtime/hooks.py"
  do
    if [ -n "$_cand" ] && [ -f "$_cand" ]; then
      printf '%s' "$_cand"
      return 0
    fi
  done
  if _top=$(git rev-parse --show-toplevel 2>/dev/null) && [ -f "$_top/.ai-sdlc/bin/hooks.py" ]; then
    printf '%s' "$_top/.ai-sdlc/bin/hooks.py"
    return 0
  fi
  return 1
}

hook_fail_closed() {
  _hfc_harness=${1:-claude}
  _hfc_reason=$2
  case "$_hfc_harness" in
    cursor)
      printf '{"permission":"deny","agent_message":"%s","user_message":"%s"}\n' "$_hfc_reason" "$_hfc_reason"
      ;;
    gemini)
      printf '{"decision":"deny","reason":"%s"}\n' "$_hfc_reason"
      ;;
    *)
      printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$_hfc_reason"
      ;;
  esac
  exit 0
}

hook_exec() {
  _he_rule=$1
  _he_harness=${2:-claude}
  _he_dir=$3
  _he_py=$(hook_find_python) || hook_fail_closed "$_he_harness" "python3 is required to run ai-sdlc hooks (fail-closed)"
  _he_eng=$(hook_find_engine "$_he_dir") || hook_fail_closed "$_he_harness" "missing .ai-sdlc/bin/hooks.py (fail-closed)"
  exec "$_he_py" "$_he_eng" run --harness "$_he_harness" "$_he_rule"
}
