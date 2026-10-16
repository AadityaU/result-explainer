-- id: q09
-- title: Delivery time by region
-- question: How many days does delivery take on average in each region, and what was the slowest?
-- columns: region=label, delivered_orders=count, avg_delivery_days=number, max_delivery_days=count
-- focus: avg_delivery_days
--
-- Delivery days are counted from the order date to the delivery date.
SELECT c.region,
       COUNT(*) AS delivered_orders,
       ROUND(AVG(julianday(o.delivery_date) - julianday(o.order_date)), 1) AS avg_delivery_days,
       CAST(MAX(julianday(o.delivery_date) - julianday(o.order_date)) AS INTEGER) AS max_delivery_days
FROM orders AS o
JOIN customers AS c ON c.customer_id = o.customer_id
WHERE o.status = 'delivered'
GROUP BY c.region
ORDER BY avg_delivery_days DESC;
