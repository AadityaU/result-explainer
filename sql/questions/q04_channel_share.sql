-- id: q04
-- title: Revenue share by sales channel
-- question: What share of net revenue came from each sales channel?
-- columns: channel=label, delivered_orders=count, net_revenue=currency, revenue_share_pct=percent
-- focus: revenue_share_pct
--
-- Shares are rounded to one decimal, so they may not add up to exactly 100.
WITH channel_revenue AS (
    SELECT o.channel,
           COUNT(DISTINCT o.order_id) AS delivered_orders,
           SUM(oi.quantity * oi.unit_price_cents * (100 - oi.discount_pct)) AS revenue_x100
    FROM orders AS o
    JOIN order_items AS oi ON oi.order_id = o.order_id
    WHERE o.status = 'delivered'
    GROUP BY o.channel
)
SELECT channel,
       delivered_orders,
       ROUND(revenue_x100 / 10000.0, 2) AS net_revenue,
       ROUND(100.0 * revenue_x100 / SUM(revenue_x100) OVER (), 1) AS revenue_share_pct
FROM channel_revenue
ORDER BY revenue_x100 DESC;
