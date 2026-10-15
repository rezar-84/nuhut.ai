#!/bin/sh
# Run one ai-sdlc hook under another harness. The hooks read a Claude Code PreToolUse
# payload and print a Claude Code decision; Gemini CLI and Cursor send nearly the same
# payload and want a different answer. This translates both ways and nothing else, so
# the rule itself lives in exactly one script.
#
#   sh adapter.sh gemini work-item-id.sh   # from .gemini/settings.json, BeforeTool
#   sh adapter.sh cursor secret-guard.sh   # from .cursor/hooks.json, beforeShellExecution
#
# Both tools export CLAUDE_PROJECT_DIR as an alias of their own project-dir variable, so
# lib.sh anchors on the project root exactly as it does under Claude Code.
set -u
harness=${1:-}
hook=${2:-}
here=$(cd "$(dirname "$0")" && pwd)

if ! command -v jq >/dev/null 2>&1 || [ -z "$harness" ] || [ ! -f "$here/$hook" ]; then
  # Allow, in the shape the harness parses: a broken adapter must not block work.
  case "$harness" in
    cursor) printf '{"permission":"allow"}\n' ;;
    *) printf '{}\n' ;;
  esac
  exit 0
fi

payload=$(cat)
case "$harness" in
  cursor)
    # beforeShellExecution puts the command at the top level; preToolUse nests it.
    payload=$(printf '%s' "$payload" | jq -c '
      {tool_name: (.tool_name // "Bash"),
       tool_input: (.tool_input // {}) + (if .command then {command: .command} else {} end)}')
    ;;
  gemini)
    # run_shell_command, write_file and replace already use command, file_path, content,
    # old_string and new_string, the same names the hooks read.
    ;;
esac

verdict=$(printf '%s' "$payload" | sh "$here/$hook")
decision=$(printf '%s' "$verdict" | jq -r '.hookSpecificOutput.permissionDecision // ""' 2>/dev/null)
reason=$(printf '%s' "$verdict" | jq -r '.hookSpecificOutput.permissionDecisionReason // ""' 2>/dev/null)
note=$(printf '%s' "$verdict" | jq -r '.systemMessage // ""' 2>/dev/null)

case "$harness" in
  cursor)
    if [ "$decision" = "deny" ]; then
      jq -cn --arg r "$reason" '{permission: "deny", agent_message: $r, user_message: $r}'
    else
      jq -cn --arg m "$note" '{permission: "allow"} + (if $m != "" then {user_message: $m} else {} end)'
    fi
    ;;
  *)
    if [ "$decision" = "deny" ]; then
      jq -cn --arg r "$reason" '{decision: "deny", reason: $r}'
    else
      jq -cn --arg m "$note" '(if $m != "" then {systemMessage: $m} else {} end)'
    fi
    ;;
esac
exit 0
