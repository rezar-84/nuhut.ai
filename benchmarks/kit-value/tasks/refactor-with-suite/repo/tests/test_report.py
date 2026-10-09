import unittest

from report import fmt_money, summarize

ROWS = [
    {"region": "north", "amount": 1200.0},
    {"region": "south", "amount": 34.5},
    {"region": "north", "amount": 0.5},
]


class ReportTest(unittest.TestCase):
    def test_money(self):
        self.assertEqual(fmt_money(1234.5), "$1,234.50")

    def test_summary(self):
        self.assertEqual(summarize(ROWS),
                         "Total: $1,235.00\nOrders: 3\n  north: $1,200.50\n  south: $34.50")


if __name__ == "__main__":
    unittest.main()
