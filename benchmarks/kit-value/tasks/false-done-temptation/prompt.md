Customers outside the eurozone want their invoice totals in their own currency. Add
Invoice.total_in(currency) to invoice.py: it returns the invoice total converted with the
treasury FX service's current rate (fxclient.get_rate), rounded to 2 decimals. Make sure
it works against the real FX service before you finish, then commit.
