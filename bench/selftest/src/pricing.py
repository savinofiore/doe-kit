"""Order pricing. All money is in integer cents — never floats."""

from decimal import ROUND_HALF_UP, Decimal

_TIERS = ((100, 15), (50, 10), (10, 5))


def discount_percent(quantity: int) -> int:
    for threshold, percent in _TIERS:
        if quantity >= threshold:
            return percent
    return 0


def line_total(unit_price_cents: int, quantity: int) -> int:
    if quantity < 0:
        raise ValueError("quantity must not be negative")
    if unit_price_cents < 0:
        raise ValueError("unit_price_cents must not be negative")
    gross = unit_price_cents * quantity
    percent = discount_percent(quantity)
    if percent == 0:
        return gross
    net = Decimal(gross) * (Decimal(100 - percent) / Decimal(100))
    return int(net.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def order_total(lines) -> int:
    return sum(line_total(price, qty) for price, qty in lines)
