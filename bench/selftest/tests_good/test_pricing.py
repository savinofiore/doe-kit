"""A suite that actually asserts. Should kill most mutants."""

import unittest

from src.pricing import discount_percent, line_total, order_total


class Tiers(unittest.TestCase):
    def test_tiers(self):
        self.assertEqual(discount_percent(0), 0)
        self.assertEqual(discount_percent(9), 0)
        self.assertEqual(discount_percent(10), 5)
        self.assertEqual(discount_percent(49), 5)
        self.assertEqual(discount_percent(50), 10)
        self.assertEqual(discount_percent(99), 10)
        self.assertEqual(discount_percent(100), 15)


class Lines(unittest.TestCase):
    def test_undiscounted(self):
        self.assertEqual(line_total(250, 4), 1000)
        self.assertEqual(line_total(250, 9), 2250)
        self.assertEqual(line_total(250, 0), 0)

    def test_discounted(self):
        self.assertEqual(line_total(250, 10), 2375)
        self.assertEqual(line_total(100, 50), 4500)
        self.assertEqual(line_total(100, 100), 8500)

    def test_rounding(self):
        self.assertEqual(line_total(55, 10), 523)
        self.assertEqual(line_total(75, 10), 713)

    def test_validation(self):
        with self.assertRaises(ValueError):
            line_total(250, -1)
        with self.assertRaises(ValueError):
            line_total(-1, 3)


class Orders(unittest.TestCase):
    def test_sums(self):
        self.assertEqual(order_total([]), 0)
        self.assertEqual(order_total([(250, 9), (100, 50)]), 6750)
