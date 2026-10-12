-- 01_monthly_kpis.sql
-- Monthly GMV, orders, active customers, AOV and month-over-month growth.
-- Techniques: aggregation, window functions (LAG, rolling AVG).
WITH m AS (
    SELECT order_month,
           SUM(order_value)            AS gmv,
           COUNT(*)                    AS orders,
           COUNT(DISTINCT customer_id) AS active_customers,
           AVG(order_value)            AS aov
    FROM order_value
    GROUP BY order_month
)
SELECT STRFTIME(order_month, '%Y-%m')                                        AS month,
       ROUND(gmv, 0)                                                         AS gmv,
       orders,
       active_customers,
       ROUND(aov, 2)                                                         AS aov,
       ROUND(100.0 * (gmv / LAG(gmv) OVER (ORDER BY order_month) - 1), 1)    AS gmv_mom_pct,
       ROUND(AVG(gmv) OVER (ORDER BY order_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0) AS gmv_3m_avg
FROM m
ORDER BY order_month;
