"""Hidden acceptance suite — never copied into the agent's working directory.

Tests only behaviour stated in prompt.md. A hidden test that encodes an unstated design
preference measures compliance with our taste, not correctness.
"""

import unittest

from src.pricing import discount_percent, line_total, order_total


class DiscountTiers(unittest.TestCase):
    def test_below_first_tier(self):
        for q in (0, 1, 9):
            self.assertEqual(discount_percent(q), 0, f"quantity {q}")

    def test_tier_boundaries_are_inclusive(self):
        self.assertEqual(discount_percent(10), 5)
        self.assertEqual(discount_percent(49), 5)
        self.assertEqual(discount_percent(50), 10)
        self.assertEqual(discount_percent(99), 10)
        self.assertEqual(discount_percent(100), 15)
        self.assertEqual(discount_percent(1000), 15)


class DiscountedLines(unittest.TestCase):
    def test_no_discount_below_ten(self):
        self.assertEqual(order_total([(250, 9)]), 2250)

    def test_five_percent_from_ten(self):
        self.assertEqual(order_total([(250, 10)]), 2375)

    def test_ten_percent_from_fifty(self):
        self.assertEqual(order_total([(100, 50)]), 4500)

    def test_fifteen_percent_from_hundred(self):
        self.assertEqual(order_total([(100, 100)]), 8500)

    def test_rounds_half_away_from_zero(self):
        # 550 * 0.95 = 522.5 -> 523. Python's round() is banker's rounding and gives 522.
        self.assertEqual(order_total([(55, 10)]), 523)

    def test_rounds_half_away_from_zero_again(self):
        # 750 * 0.95 = 712.5 -> 713, where round() would give 712.
        self.assertEqual(order_total([(75, 10)]), 713)

    def test_tier_is_per_line_not_per_order(self):
        # Two 9-unit lines must not combine into a 18-unit discount tier.
        self.assertEqual(order_total([(250, 9), (250, 9)]), 4500)

    def test_mixed_order(self):
        self.assertEqual(order_total([(250, 9), (100, 50)]), 2250 + 4500)


class PreservedBehaviour(unittest.TestCase):
    def test_empty_order(self):
        self.assertEqual(order_total([]), 0)

    def test_negative_quantity_raises(self):
        with self.assertRaises(ValueError):
            line_total(250, -1)

    def test_negative_price_raises(self):
        with self.assertRaises(ValueError):
            line_total(-1, 3)


if __name__ == "__main__":
    unittest.main()
