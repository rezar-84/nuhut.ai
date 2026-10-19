import json
import os
import tempfile
import unittest

from export import export_orders
from parse import parse_orders


def csv_file(text):
    handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
    handle.write(text)
    handle.close()
    return handle.name


class Accept(unittest.TestCase):
    def test_code_flows_end_to_end(self):
        path = csv_file("order_id,sku,quantity,discount_code\nC-1,ABC-1234,1,SAVE10\n")
        exported = json.loads(export_orders(parse_orders(path)))
        self.assertEqual(exported[0]["discount_code"], "SAVE10")

    def test_invalid_code_is_rejected(self):
        for bad in ("save10", "TOO-LONG-CODE-123", "SAVE 10", "ABCDEFGHIJKLM"):
            path = csv_file("order_id,sku,quantity,discount_code\nC-1,ABC-1234,1,%s\n" % bad)
            with self.assertRaises(ValueError, msg=bad):
                parse_orders(path)

    def test_blank_code_means_no_code(self):
        path = csv_file("order_id,sku,quantity,discount_code\nC-1,ABC-1234,1,\n")
        order = parse_orders(path)[0]
        self.assertIsNone(order.discount_code)

    def test_files_from_before_the_column_still_load(self):
        # The easy edge to miss: re-imported exports have no discount_code column.
        here = os.getcwd()
        orders = parse_orders(os.path.join(here, "data", "orders-2023-q4.csv"))
        self.assertEqual([o.discount_code for o in orders], [None, None])
        self.assertEqual(len(json.loads(export_orders(orders))), 2)


if __name__ == "__main__":
    unittest.main()
