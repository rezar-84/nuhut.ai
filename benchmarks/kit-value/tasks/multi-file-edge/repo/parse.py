"""Read orders from CSV exports."""
import csv

from order import Order
from validate import check_quantity, check_sku


def parse_orders(path):
    with open(path, newline="") as handle:
        return [Order(row["order_id"], check_sku(row["sku"]), check_quantity(row["quantity"]))
                for row in csv.DictReader(handle)]
