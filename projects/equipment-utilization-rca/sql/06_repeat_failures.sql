-- 06_repeat_failures.sql
-- Repeat failures: the same unit failing on the same system within 30 days of
-- the previous repair, a sign the root cause was not fixed.
WITH seq AS (
    SELECT unit_id, site, model, system, start_time,
           LAG(end_time) OVER (PARTITION BY unit_id, system ORDER BY start_time) AS prev_end
    FROM events WHERE event_type = 'Breakdown'
)
SELECT system,
       COUNT(*)                                                         AS breakdowns,
       SUM(CASE WHEN DATE_DIFF('day', prev_end, start_time) <= 30 THEN 1 ELSE 0 END) AS repeat_within_30d,
       ROUND(100.0 * AVG(CASE WHEN DATE_DIFF('day', prev_end, start_time) <= 30 THEN 1 ELSE 0 END), 1) AS repeat_pct
FROM seq
GROUP BY system
ORDER BY repeat_pct DESC;
