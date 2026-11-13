from decimal import Decimal
import money


def export_row(sku, decimal_price):
    # Passes a Decimal instance directly into money.to_cents
    return "%s,%d" % (sku, money.to_cents(Decimal(str(decimal_price))))
