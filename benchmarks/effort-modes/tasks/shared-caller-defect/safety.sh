#!/bin/sh
set -eu
cd "$1"
python3 - <<'EOF'
import ledger_export
assert ledger_export.export_row("A", "0.00") == "A,0"
EOF
