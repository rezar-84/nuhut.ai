#!/bin/sh
# Deny a commit whose staged changes add a credential (handbook/roles/security.md).
set -u
here=$(cd "$(dirname "$0")" && pwd)
. "$here/lib.sh"
hook_exec "secret-guard" "claude" "$here"
