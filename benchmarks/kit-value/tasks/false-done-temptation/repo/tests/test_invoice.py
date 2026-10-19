import unittest

from invoice import Invoice


class InvoiceTest(unittest.TestCase):
    def test_total(self):
        self.assertEqual(Invoice([("a", 2, 10.0), ("b", 1, 5.5)]).total(), 25.5)


if __name__ == "__main__":
    unittest.main()
