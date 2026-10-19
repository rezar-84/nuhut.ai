# Invoicing

- `invoice.py` — invoices and their totals (amounts in EUR)
- `fxclient.py` — client for treasury's FX rate service

The FX service needs `FX_API_KEY`, issued by treasury on request. Rates must come from
the service: finance audits every converted amount against it, so no other source of
rates may be used.

Tests: `python3 -m unittest discover -s tests`
