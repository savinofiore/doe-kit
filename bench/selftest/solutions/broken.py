"""A plausible-looking wrong answer, used to prove the scorer notices.

Two defects, one per metric it is meant to expose:
  * float maths and round() — banker's rounding, so 522.5 becomes 522. The hidden suite
    catches it; the agent's own tests would not.
  * the negative-price guard is gone. The workdir's tests no longer check it; the fixture's
    original suite, restored at scoring time, does.
"""


def discount_percent(quantity: int) -> int:
    if quantity >= 100:
        return 15
    if quantity >= 50:
        return 10
    if quantity >= 10:
        return 5
    return 0


def line_total(unit_price_cents: int, quantity: int) -> int:
    if quantity < 0:
        raise ValueError("quantity must not be negative")
    gross = unit_price_cents * quantity
    return round(gross * (100 - discount_percent(quantity)) / 100)


def order_total(lines) -> int:
    return sum(line_total(price, qty) for price, qty in lines)
