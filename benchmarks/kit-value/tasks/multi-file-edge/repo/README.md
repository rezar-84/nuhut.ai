# Orders

- `order.py` — the Order record
- `parse.py` — reads orders from CSV exports
- `validate.py` — field validation
- `export.py` — JSON export for the warehouse

`data/` holds the CSV exports we still re-import, back to 2023.

Tests: `python3 -m unittest discover -s tests`
