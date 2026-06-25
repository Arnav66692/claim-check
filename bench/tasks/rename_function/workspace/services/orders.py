from services.pricing import compute_total


def order_value(order):
    return compute_total(order["items"])
