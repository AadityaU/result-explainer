-- id: q01
-- title: Monthly revenue and order count
-- question: How did net revenue and the number of delivered orders change month by month in 2025?
-- columns: month=label, delivered_orders=count, net_revenue=currency
-- focus: net_revenue
--
-- Net revenue = quantity x unit price x (100 - discount_pct) / 100 over delivered
-- orders, before returns. Summed as integer cents x 100 and divided once at the end.
SELECT substr(o.order_date, 1, 7) AS month,
       COUNT(DISTINCT o.order_id) AS delivered_orders,
       ROUND(SUM(oi.quantity * oi.unit_price_cents * (100 - oi.discount_pct)) / 10000.0, 2) AS net_revenue
FROM orders AS o
JOIN order_items AS oi ON oi.order_id = o.order_id
WHERE o.status = 'delivered'
GROUP BY month
ORDER BY month;
