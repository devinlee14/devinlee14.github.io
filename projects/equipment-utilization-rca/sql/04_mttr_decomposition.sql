-- 04_mttr_decomposition.sql
-- Where does repair time go? Hands-on repair vs waiting for parts vs waiting for a mechanic.
SELECT site,
       COUNT(*)                                 AS breakdowns,
       ROUND(AVG(repair_h), 1)                  AS repair_h,
       ROUND(AVG(waiting_parts_h), 1)           AS waiting_parts_h,
       ROUND(AVG(waiting_mechanic_h), 1)        AS waiting_mechanic_h,
       ROUND(100 * SUM(waiting_parts_h) / SUM(duration_h), 1) AS parts_share_pct,
       ROUND(QUANTILE_CONT(waiting_parts_h, 0.9) FILTER (WHERE waiting_parts_h > 0), 1) AS p90_parts_wait_h
FROM events
WHERE event_type = 'Breakdown'
GROUP BY site
ORDER BY waiting_parts_h DESC;
