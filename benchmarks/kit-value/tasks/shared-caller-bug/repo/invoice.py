from pricing import apply_discount


def invoice_line(quantity, unit_price, discount_percent=0):
    return apply_discount(quantity * unit_price, discount_percent)
