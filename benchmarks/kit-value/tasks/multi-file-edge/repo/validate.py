"""Field validation."""
import re

SKU = re.compile(r"^[A-Z]{3}-[0-9]{4}$")


def check_sku(value):
    if not SKU.match(value):
        raise ValueError("bad sku: %r" % value)
    return value


def check_quantity(value):
    quantity = int(value)
    if quantity < 1:
        raise ValueError("quantity must be positive: %r" % value)
    return quantity
