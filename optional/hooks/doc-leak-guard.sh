#!/bin/sh
# Deny a file write that contains a credential ({{DOCS_DIR}}/process/12-sensitive-data-in-records.md).
set -u
here=$(cd "$(dirname "$0")" && pwd)
. "$here/lib.sh"
hook_exec "doc-leak-guard" "claude" "$here"
