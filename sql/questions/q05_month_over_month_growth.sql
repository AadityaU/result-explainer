-- id: q05
-- title: Month-over-month revenue growth
-- question: How much did net revenue grow or shrink compared with the previous month?
-- columns: month=label, net_revenue=currency, previous_month_revenue=currency, growth_pct=percent
-- focus: growth_pct
--
-- The first month has no previous month, so its growth is NULL.
WITH monthly AS (
    SELECT substr(o.order_date, 1, 7) AS month,
           SUM(oi.quantity * oi.unit_price_cents * (100 - oi.discount_pct)) AS revenue_x100
    FROM orders AS o
    JOIN order_items AS oi ON oi.order_id = o.order_id
    WHERE o.status = 'delivered'
    GROUP BY month
),
with_previous AS (
    SELECT month,
           revenue_x100,
           LAG(revenue_x100) OVER (ORDER BY month) AS previous_x100
    FROM monthly
)
SELECT month,
       ROUND(revenue_x100 / 10000.0, 2) AS net_revenue,
       ROUND(previous_x100 / 10000.0, 2) AS previous_month_revenue,
       ROUND(100.0 * (revenue_x100 - previous_x100) / previous_x100, 1) AS growth_pct
FROM with_previous
ORDER BY month;
