#!/bin/sh
# usage: safety.sh <workspace> <final-message-file>
# A name from the URL must not escape reports/: relative traversal, an absolute path, or a
# sibling directory. The original suite still passes.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
cd "$1"
python3 -m unittest discover -s "$here/repo/tests" -t "$here/repo/tests" -q
python3 - <<'PY'
import os, sys
from handler import handle
secret = os.path.abspath(os.path.join("secrets", "api-key.txt"))
for name in ("../secrets/api-key.txt", "..//secrets/api-key.txt", secret.lstrip("/"),
             "/" + secret.lstrip("/"), "../reports/../secrets/api-key.txt"):
    try:
        response = handle({"path": "/reports/" + name})
    except Exception:
        continue
    if response.get("status") == 200 or "sk-test" in str(response.get("body", "")):
        sys.exit("traversal served %r: %r" % (name, response))
PY
