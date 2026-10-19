"""JSON export for the warehouse."""
import json


def export_orders(orders):
    return json.dumps([{"order_id": o.order_id, "sku": o.sku, "quantity": o.quantity}
                       for o in orders], sort_keys=True)
