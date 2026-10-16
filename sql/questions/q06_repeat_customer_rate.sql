-- id: q06
-- title: Repeat-customer rate
-- question: What share of customers who received an order in 2025 came back for at least one more?
-- columns: customers_with_orders=count, repeat_customers=count, repeat_rate_pct=percent
-- focus: repeat_rate_pct
--
-- A repeat customer has two or more delivered orders.
WITH per_customer AS (
    SELECT customer_id,
           COUNT(*) AS delivered_orders
    FROM orders
    WHERE status = 'delivered'
    GROUP BY customer_id
)
SELECT COUNT(*) AS customers_with_orders,
       SUM(delivered_orders >= 2) AS repeat_customers,
       ROUND(100.0 * SUM(delivered_orders >= 2) / COUNT(*), 1) AS repeat_rate_pct
FROM per_customer;
