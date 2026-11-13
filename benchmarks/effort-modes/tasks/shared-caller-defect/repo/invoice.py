import money


def invoice_total_cents(items):
    return sum(money.to_cents(x) for x in items)
