-- id: q10
-- title: Orders that missed the 14-day delivery promise
-- question: Which delivered orders took more than 14 days from order to delivery?
-- columns: order_id=label, region=label, order_date=label, delivery_days=count
-- focus: delivery_days
--
-- An empty result is the good outcome: every delivered order met the promise.
SELECT o.order_id,
       c.region,
       o.order_date,
       CAST(julianday(o.delivery_date) - julianday(o.order_date) AS INTEGER) AS delivery_days
FROM orders AS o
JOIN customers AS c ON c.customer_id = o.customer_id
WHERE o.status = 'delivered'
  AND julianday(o.delivery_date) - julianday(o.order_date) > 14
ORDER BY delivery_days DESC, o.order_id;
