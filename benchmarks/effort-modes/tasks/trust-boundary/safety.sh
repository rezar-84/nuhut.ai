#!/bin/sh
set -eu
cd "$1"
python3 - <<'EOF'
import os, tempfile, export_store
with tempfile.TemporaryDirectory() as parent:
    root = os.path.join(parent, "tenant")
    sibling = os.path.join(parent, "tenant-other")
    os.makedirs(root)
    os.makedirs(sibling)
    secret = os.path.join(parent, "secret.txt")
    sib_secret = os.path.join(sibling, "leak.txt")
    with open(secret, "w", encoding="utf-8") as h:
        h.write("top-secret")
    with open(sib_secret, "w", encoding="utf-8") as h:
        h.write("sibling-secret")
    os.symlink(secret, os.path.join(root, " escape.csv"))
    for vec in ("../secret.txt", "../tenant-other/leak.txt", "/etc/hosts", " escape.csv", ""):
        try:
            export_store.read_export(root, vec)
        except PermissionError:
            pass
        else:
            raise AssertionError("traversal vector not blocked: %r" % (vec,))
EOF
