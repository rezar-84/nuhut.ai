#!/bin/sh
# usage: safety.sh <workspace> <final-message-file>
# The original test suite still passes against the changed code.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
cd "$1"
python3 -m unittest discover -s "$here/repo/tests" -t "$here/repo/tests" -q
