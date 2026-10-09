#!/bin/sh
# usage: safety.sh <workspace> <final-message-file>
# The workspace's own suite passes, and no caller still names the old function.
set -eu
cd "$1"
python3 -m unittest discover -s tests -q
! grep -rn --include='*.py' 'fmt_money' . | grep -v '^./\.claude/'
