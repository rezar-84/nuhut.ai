import unittest
import invoice
import refund


class BillingTest(unittest.TestCase):
    def test_whole_dollars(self):
        self.assertEqual(invoice.invoice_total_cents([10, 5]), 1500)
        self.assertEqual(refund.refund_cents("2.50"), 250)


if __name__ == "__main__":
    unittest.main()
