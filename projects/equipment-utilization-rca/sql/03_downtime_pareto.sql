-- 03_downtime_pareto.sql
-- Which systems cause the most unplanned downtime? (Pareto with running share)
SELECT system,
       COUNT(*)                                                      AS breakdowns,
       ROUND(SUM(duration_h), 0)                                     AS downtime_h,
       ROUND(AVG(duration_h), 1)                                     AS avg_h,
       ROUND(100 * SUM(SUM(duration_h)) OVER (ORDER BY SUM(duration_h) DESC
             ROWS UNBOUNDED PRECEDING) / SUM(SUM(duration_h)) OVER (), 1) AS cumulative_pct
FROM events
WHERE event_type = 'Breakdown'
GROUP BY system
ORDER BY downtime_h DESC;
