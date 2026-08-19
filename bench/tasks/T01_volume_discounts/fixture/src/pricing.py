"""Order pricing. All money is in integer cents — never floats."""


def line_total(unit_price_cents: int, quantity: int) -> int:
    """Total for one order line, in cents."""
    if quantity < 0:
        raise ValueError("quantity must not be negative")
    if unit_price_cents < 0:
        raise ValueError("unit_price_cents must not be negative")
    return unit_price_cents * quantity


def order_total(lines) -> int:
    """Total for a list of (unit_price_cents, quantity) lines, in cents."""
    return sum(line_total(price, qty) for price, qty in lines)
