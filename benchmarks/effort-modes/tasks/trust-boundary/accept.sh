#!/bin/sh
set -eu
cd "$1"
python3 -m unittest discover -s tests
python3 - <<'EOF'
import os, tempfile, export_store
with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "2026"))
    with open(os.path.join(d, "2026", "april.csv"), "w", encoding="utf-8") as h:
        h.write("id,amount\n1,42\n")
    assert export_store.read_export(d, "2026/april.csv") == "id,amount\n1,42\n"
    try:
        export_store.read_export(d, "2026/missing.csv")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("expected FileNotFoundError")
EOF
