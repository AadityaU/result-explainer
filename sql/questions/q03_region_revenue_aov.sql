-- id: q03
-- title: Revenue and average order value by region
-- question: How do net revenue and average order value differ across customer regions?
-- columns: region=label, delivered_orders=count, net_revenue=currency, avg_order_value=currency
-- focus: net_revenue
--
-- Average order value = net revenue / delivered orders in the region.
WITH order_revenue AS (
    SELECT o.order_id,
           c.region,
           SUM(oi.quantity * oi.unit_price_cents * (100 - oi.discount_pct)) AS revenue_x100
    FROM orders AS o
    JOIN customers AS c ON c.customer_id = o.customer_id
    JOIN order_items AS oi ON oi.order_id = o.order_id
    WHERE o.status = 'delivered'
    GROUP BY o.order_id
)
SELECT region,
       COUNT(*) AS delivered_orders,
       ROUND(SUM(revenue_x100) / 10000.0, 2) AS net_revenue,
       ROUND(SUM(revenue_x100) / 10000.0 / COUNT(*), 2) AS avg_order_value
FROM order_revenue
GROUP BY region
ORDER BY net_revenue DESC;
