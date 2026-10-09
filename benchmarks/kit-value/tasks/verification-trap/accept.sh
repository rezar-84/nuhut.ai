#!/bin/sh
# usage: accept.sh <workspace>
# Hidden acceptance tests, run against the workspace's code. The agent never sees them.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
cd "$1"
python3 -m unittest discover -s "$here/hidden" -t "$here/hidden" -q
