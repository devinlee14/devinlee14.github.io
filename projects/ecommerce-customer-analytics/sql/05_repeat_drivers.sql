-- 05_repeat_drivers.sql
-- Does the FIRST order experience predict whether a customer ever buys again?
-- Compares repeat-purchase rate by first-order review score and delivery outcome.
-- Techniques: ROW_NUMBER to isolate first orders, LEFT JOIN, conditional aggregation.
WITH ranked AS (
    SELECT ov.*, r.review_score,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY purchased_at) AS rn,
           COUNT(*)     OVER (PARTITION BY customer_id)                       AS total_orders
    FROM order_value ov
    LEFT JOIN reviews r USING (order_id)
),
first_orders AS (
    SELECT *,
           CASE WHEN delivered_at IS NULL           THEN 'not delivered'
                WHEN delivered_at > estimated_at    THEN 'late'
                ELSE 'on time' END                  AS delivery_outcome
    FROM ranked
    WHERE rn = 1 AND purchased_at < '2018-03-01'    -- give every customer >= 6 months to return
)
SELECT 'review_score' AS dimension, CAST(ROUND(review_score) AS VARCHAR) AS value,
       COUNT(*) AS customers,
       ROUND(100.0 * AVG(CASE WHEN total_orders > 1 THEN 1 ELSE 0 END), 2) AS repeat_rate_pct
FROM first_orders WHERE review_score IS NOT NULL GROUP BY 2
UNION ALL
SELECT 'delivery', delivery_outcome, COUNT(*),
       ROUND(100.0 * AVG(CASE WHEN total_orders > 1 THEN 1 ELSE 0 END), 2)
FROM first_orders GROUP BY 2
ORDER BY dimension, value;
