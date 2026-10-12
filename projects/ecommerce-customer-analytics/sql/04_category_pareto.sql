-- 04_category_pareto.sql
-- Which categories drive revenue? Cumulative share (Pareto / 80-20).
-- Techniques: running SUM() OVER, ROW_NUMBER, share-of-total.
WITH cat AS (
    SELECT i.category, SUM(i.price) AS revenue, COUNT(DISTINCT i.order_id) AS orders
    FROM items i JOIN orders o USING (order_id)
    GROUP BY i.category
)
SELECT ROW_NUMBER() OVER (ORDER BY revenue DESC)                          AS rank,
       category,
       ROUND(revenue, 0)                                                  AS revenue,
       orders,
       ROUND(100.0 * revenue / SUM(revenue) OVER (), 2)                   AS pct_revenue,
       ROUND(100.0 * SUM(revenue) OVER (ORDER BY revenue DESC
             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) / SUM(revenue) OVER (), 1) AS cumulative_pct
FROM cat
ORDER BY revenue DESC;
