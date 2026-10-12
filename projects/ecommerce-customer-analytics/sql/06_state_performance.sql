-- 06_state_performance.sql
-- Revenue, AOV and freight burden by customer state.
SELECT state,
       COUNT(*)                                        AS orders,
       ROUND(SUM(order_value), 0)                      AS gmv,
       ROUND(AVG(order_value), 2)                      AS aov,
       ROUND(100.0 * SUM(freight_value) / SUM(order_value), 1) AS freight_share_pct
FROM order_value
GROUP BY state
ORDER BY gmv DESC;
