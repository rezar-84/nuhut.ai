#!/bin/sh
# Deny a commit whose message carries no work item ID (handbook/process/07-traceability.md).
set -u
here=$(cd "$(dirname "$0")" && pwd)
. "$here/lib.sh"
hook_exec "work-item-id" "claude" "$here"
