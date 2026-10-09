import unittest

from checkout import checkout_total
from invoice import invoice_line
from pricing import apply_discount


class Accept(unittest.TestCase):
    def test_checkout(self):
        self.assertEqual(checkout_total([20.0, 30.0], 10), 45.0)

    def test_invoice_shares_the_fix(self):
        self.assertEqual(invoice_line(2, 50.0, 10), 90.0)

    def test_helper_contract(self):
        self.assertEqual(apply_discount(100.0, 0), 100.0)
        self.assertEqual(apply_discount(100.0, 100), 0.0)
