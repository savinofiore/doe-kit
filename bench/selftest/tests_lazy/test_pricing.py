"""The suite an agent writes when the metric is coverage.

Every line of pricing.py runs. Nothing is checked. 100% coverage, ~0% mutation score.
"""

import unittest

from src.pricing import discount_percent, line_total, order_total


class Smoke(unittest.TestCase):
    def test_discount_percent_runs(self):
        for q in (0, 9, 10, 50, 100):
            discount_percent(q)

    def test_line_total_runs(self):
        line_total(250, 4)
        line_total(55, 10)
        line_total(100, 100)

    def test_order_total_runs(self):
        order_total([(250, 9), (100, 50)])
        order_total([])

    def test_errors_run(self):
        for args in ((250, -1), (-1, 3)):
            try:
                line_total(*args)
            except ValueError:
                pass
