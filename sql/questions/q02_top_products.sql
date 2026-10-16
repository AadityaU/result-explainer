-- id: q02
-- title: Top 10 products by net revenue
-- question: Which 10 products earned the most net revenue in 2025, and how many units did each sell?
-- columns: rank=count, product=label, category=label, units_sold=count, net_revenue=currency
-- focus: net_revenue
--
-- Ties on revenue are broken by product_id so the ranking is stable.
WITH product_revenue AS (
    SELECT p.product_id,
           p.name,
           p.category,
           SUM(oi.quantity) AS units_sold,
           SUM(oi.quantity * oi.unit_price_cents * (100 - oi.discount_pct)) AS revenue_x100
    FROM order_items AS oi
    JOIN orders AS o ON o.order_id = oi.order_id
    JOIN products AS p ON p.product_id = oi.product_id
    WHERE o.status = 'delivered'
    GROUP BY p.product_id
)
SELECT ROW_NUMBER() OVER (ORDER BY revenue_x100 DESC, product_id) AS rank,
       name AS product,
       category,
       units_sold,
       ROUND(revenue_x100 / 10000.0, 2) AS net_revenue
FROM product_revenue
ORDER BY rank
LIMIT 10;
