#!/bin/sh
# Run one ai-sdlc hook under Gemini CLI or Cursor via the unified Python hook engine.
#
#   sh adapter.sh gemini work-item-id.sh   # from .gemini/settings.json, BeforeTool
#   sh adapter.sh cursor secret-guard.sh   # from .cursor/hooks.json, beforeShellExecution
set -u
harness=${1:-}
hook=${2:-}
here=$(cd "$(dirname "$0")" && pwd)

if [ -z "$harness" ] || [ -z "$hook" ] || [ ! -f "$here/$hook" ]; then
  # If the named hook script is absent on disk, allow in the harness's shape.
  case "$harness" in
    cursor) printf '{"permission":"allow"}\n' ;;
    *) printf '{}\n' ;;
  esac
  exit 0
fi

. "$here/lib.sh"
hook_exec "$hook" "$harness" "$here"
