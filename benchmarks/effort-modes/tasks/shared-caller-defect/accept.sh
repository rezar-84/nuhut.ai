#!/bin/sh
set -eu
cd "$1"
python3 -m unittest discover -s tests
python3 - <<'EOF'
from decimal import Decimal
import money, invoice, refund, ledger_export
assert money.to_cents("19.99") == 1999
assert money.to_cents(19.99) == 1999
assert money.to_cents("19.995") == 2000
assert invoice.invoice_total_cents(["0.10", "0.20", "19.99"]) == 2029
assert refund.refund_cents(Decimal("4.005")) == 401
assert ledger_export.export_row("SKU-1", Decimal("19.995")) == "SKU-1,2000"
EOF
