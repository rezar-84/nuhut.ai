#!/bin/sh
# Deny an edit to a test locked in .ai-sdlc/test-lock.txt ({{DOCS_DIR}}/process/05-change-control.md).
set -u
here=$(cd "$(dirname "$0")" && pwd)
. "$here/lib.sh"
hook_exec "test-lock" "claude" "$here"
