from pricing import apply_discount


def checkout_total(prices, discount_percent=0):
    return apply_discount(sum(prices), discount_percent)
