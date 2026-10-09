"""Price arithmetic shared by checkout and invoicing."""


def apply_discount(total, percent):
    """Return total after a percentage discount. percent is 0-100, e.g. 10 for 10%."""
    return round(total - total * percent, 2)
