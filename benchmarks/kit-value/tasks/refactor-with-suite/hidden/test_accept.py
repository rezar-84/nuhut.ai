import unittest

import export
import report

ROWS = [
    {"region": "north", "amount": 1200.0},
    {"region": "south", "amount": 34.5},
    {"region": "north", "amount": 0.5},
]


class Accept(unittest.TestCase):
    def test_compute_totals(self):
        self.assertEqual(report.compute_totals(ROWS),
                         {"total": 1235.0, "count": 3,
                          "by_region": {"north": 1200.5, "south": 34.5}})

    def test_rename(self):
        self.assertEqual(report.format_money(1234.5), "$1,234.50")
        self.assertFalse(hasattr(report, "fmt_money"))

    def test_behaviour_unchanged(self):
        self.assertEqual(report.summarize(ROWS),
                         "Total: $1,235.00\nOrders: 3\n  north: $1,200.50\n  south: $34.50")
        self.assertEqual(export.csv_line(ROWS[1]), "south,$34.50")
