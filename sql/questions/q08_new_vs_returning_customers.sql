-- id: q08
-- title: New vs returning customers by quarter
-- question: Each quarter, how many active customers were new and how many had bought before?
-- columns: quarter=label, active_customers=count, new_customers=count, returning_customers=count
-- focus: new_customers
--
-- A customer is new in the quarter of their first delivered order in the dataset.
-- The data starts in 2025, so every customer in the first quarter counts as new.
WITH delivered AS (
    SELECT customer_id,
           strftime('%Y', order_date) || '-Q' || ((CAST(strftime('%m', order_date) AS INTEGER) + 2) / 3) AS quarter
    FROM orders
    WHERE status = 'delivered'
),
first_quarter AS (
    SELECT customer_id,
           MIN(quarter) AS first_quarter
    FROM delivered
    GROUP BY customer_id
),
active AS (
    SELECT DISTINCT quarter, customer_id
    FROM delivered
)
SELECT a.quarter,
       COUNT(*) AS active_customers,
       SUM(a.quarter = f.first_quarter) AS new_customers,
       SUM(a.quarter > f.first_quarter) AS returning_customers
FROM active AS a
JOIN first_quarter AS f ON f.customer_id = a.customer_id
GROUP BY a.quarter
ORDER BY a.quarter;
