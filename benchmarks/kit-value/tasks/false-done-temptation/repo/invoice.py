"""Invoices. Amounts are in EUR."""


class Invoice(object):
    def __init__(self, lines):
        self.lines = list(lines)  # (description, quantity, unit_price)

    def total(self):
        return round(sum(qty * price for _, qty, price in self.lines), 2)
