import unittest

from src.pricing import line_total, order_total


class LineTotal(unittest.TestCase):
    def test_multiplies(self):
        self.assertEqual(line_total(250, 4), 1000)

    def test_zero_quantity(self):
        self.assertEqual(line_total(250, 0), 0)

    def test_negative_quantity_raises(self):
        with self.assertRaises(ValueError):
            line_total(250, -1)

    def test_negative_price_raises(self):
        with self.assertRaises(ValueError):
            line_total(-1, 3)


class OrderTotal(unittest.TestCase):
    def test_sums_lines(self):
        self.assertEqual(order_total([(250, 2), (100, 3)]), 800)

    def test_empty_order(self):
        self.assertEqual(order_total([]), 0)


if __name__ == "__main__":
    unittest.main()
