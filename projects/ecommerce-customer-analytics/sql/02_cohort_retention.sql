-- 02_cohort_retention.sql
-- Monthly acquisition cohorts: % of customers who come back N months later.
-- Techniques: CTEs, MIN() OVER (PARTITION BY), DATE_DIFF, conditional pivot.
WITH first_purchase AS (
    SELECT customer_id, order_month,
           MIN(order_month) OVER (PARTITION BY customer_id) AS cohort_month
    FROM orders
),
activity AS (
    SELECT DISTINCT customer_id, cohort_month,
           DATE_DIFF('month', cohort_month, order_month) AS month_number
    FROM first_purchase
),
cohort_size AS (
    SELECT cohort_month, COUNT(DISTINCT customer_id) AS customers
    FROM activity WHERE month_number = 0 GROUP BY cohort_month
)
SELECT STRFTIME(a.cohort_month, '%Y-%m') AS cohort,
       s.customers,
       a.month_number,
       COUNT(DISTINCT a.customer_id)                              AS active,
       ROUND(100.0 * COUNT(DISTINCT a.customer_id) / s.customers, 2) AS retention_pct
FROM activity a
JOIN cohort_size s USING (cohort_month)
WHERE a.month_number <= 12
GROUP BY a.cohort_month, s.customers, a.month_number
ORDER BY a.cohort_month, a.month_number;
