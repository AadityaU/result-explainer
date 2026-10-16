-- id: q07
-- title: Return rate by category
-- question: Which product categories have the highest share of units returned?
-- columns: category=label, units_sold=count, units_returned=count, return_rate_pct=percent
-- focus: return_rate_pct
--
-- Return rate = units returned / units sold on delivered orders.
WITH sold AS (
    SELECT p.category,
           SUM(oi.quantity) AS units_sold
    FROM order_items AS oi
    JOIN orders AS o ON o.order_id = oi.order_id
    JOIN products AS p ON p.product_id = oi.product_id
    WHERE o.status = 'delivered'
    GROUP BY p.category
),
returned AS (
    SELECT p.category,
           SUM(r.quantity) AS units_returned
    FROM returns AS r
    JOIN products AS p ON p.product_id = r.product_id
    GROUP BY p.category
)
SELECT s.category,
       s.units_sold,
       COALESCE(r.units_returned, 0) AS units_returned,
       ROUND(100.0 * COALESCE(r.units_returned, 0) / s.units_sold, 1) AS return_rate_pct
FROM sold AS s
LEFT JOIN returned AS r ON r.category = s.category
ORDER BY return_rate_pct DESC, s.category;
