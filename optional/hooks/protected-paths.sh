#!/bin/sh
# Deny an edit to a single-writer path in .ai-sdlc/protected.txt ({{DOCS_DIR}}/process/10-multi-agent.md).
set -u
here=$(cd "$(dirname "$0")" && pwd)
. "$here/lib.sh"
hook_exec "protected-paths" "claude" "$here"
