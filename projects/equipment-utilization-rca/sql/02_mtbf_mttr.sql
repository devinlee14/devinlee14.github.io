-- 02_mtbf_mttr.sql
-- Reliability by site and model: MTBF (operating hours per breakdown) and
-- MTTR (mean hours to restore), plus breakdowns per 1,000 operating hours.
WITH op AS (
    SELECT site, model, SUM(operating_h) AS operating_h FROM daily GROUP BY ALL
),
bd AS (
    SELECT site, model, COUNT(*) AS breakdowns, AVG(duration_h) AS mttr_h
    FROM events WHERE event_type = 'Breakdown' GROUP BY ALL
)
SELECT op.site, op.model, breakdowns,
       ROUND(operating_h / breakdowns, 0)          AS mtbf_h,
       ROUND(mttr_h, 1)                            AS mttr_h,
       ROUND(1000.0 * breakdowns / operating_h, 2) AS breakdowns_per_1000h
FROM op JOIN bd USING (site, model)
ORDER BY op.site, op.model;
