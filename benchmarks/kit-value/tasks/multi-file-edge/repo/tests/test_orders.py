import json
import os
import unittest

from export import export_orders
from parse import parse_orders

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")


class OrdersTest(unittest.TestCase):
    def test_parse_and_export(self):
        orders = parse_orders(os.path.join(DATA, "orders-2026-09.csv"))
        exported = json.loads(export_orders(orders))
        self.assertEqual(len(exported), 1)
        self.assertEqual((exported[0]["order_id"], exported[0]["sku"], exported[0]["quantity"]),
                         ("B-200", "ABC-1234", 1))


if __name__ == "__main__":
    unittest.main()
