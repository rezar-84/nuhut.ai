#!/bin/sh
# Deny a command matching .ai-sdlc/gates.txt or mutating guard/test-lock files without AI_SDLC_APPROVAL.
set -u
here=$(cd "$(dirname "$0")" && pwd)
. "$here/lib.sh"
hook_exec "approval-gate" "claude" "$here"
