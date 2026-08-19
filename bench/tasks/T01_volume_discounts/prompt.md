Add volume discounts to order pricing.

- A line qualifies for a discount based on **that line's quantity**: 5% from 10 units, 10%
  from 50 units, 15% from 100 units. Below 10 units there is no discount.
- The discount applies to that line's total. The **discounted line total** is then rounded to
  the nearest whole cent, **half away from zero** — 522.5 becomes 523, not 522.
- `order_total` returns the sum of the discounted line totals.
- Expose a helper `discount_percent(quantity)` returning the applicable rate as an integer
  percentage (0, 5, 10 or 15).
- Negative quantities and negative prices keep raising `ValueError` as they do today.
