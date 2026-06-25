from services.pricing import compute_total


def summarize(orders):
    return sum(compute_total(o["items"]) for o in orders)
