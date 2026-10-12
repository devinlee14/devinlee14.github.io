-- 05_pm_compliance_vs_failures.sql
-- Does running past the PM due point increase breakdowns?
-- 1) PM compliance per site: service done within +25 h of the due hour-meter.
-- 2) Breakdown rate per 1,000 h while PM was overdue vs on schedule.
--    Overdue operating hours are reconstructed from the daily hour-meter with
--    window functions: each day is matched to the next PM due point.
WITH pm_flag AS (
    SELECT u.site, p.*, (actual_hour_meter - due_hour_meter) <= 25 AS on_time
    FROM pm p JOIN units u USING (unit_id)
),
compliance AS (
    SELECT site, COUNT(*) AS pm_services,
           ROUND(100.0 * AVG(CASE WHEN on_time THEN 1 ELSE 0 END), 1) AS pm_compliance_pct,
           ROUND(AVG(GREATEST(actual_hour_meter - due_hour_meter, 0)), 0) AS avg_hours_late
    FROM pm_flag GROUP BY site
),
day_hm AS (   -- hour-meter at the start of each day and the last PM before it
    SELECT d.unit_id, d.site, d.date, d.operating_h,
           LAG(d.hour_meter_end, 1, u.hour_meter_start) OVER w AS hm_start,
           u.hour_meter_start
    FROM daily d JOIN units u USING (unit_id)
    WINDOW w AS (PARTITION BY d.unit_id ORDER BY d.date)
),
last_pm AS (
    SELECT h.*,
           COALESCE((SELECT MAX(p.actual_hour_meter) FROM pm p
                     WHERE p.unit_id = h.unit_id AND p.service_date < h.date),
                    FLOOR(h.hour_meter_start / 250) * 250)          AS last_pm_hm
    FROM day_hm h
),
exposure AS (
    SELECT site,
           SUM(CASE WHEN hm_start > FLOOR(last_pm_hm / 250) * 250 + 250 + 25 THEN operating_h ELSE 0 END) AS overdue_h,
           SUM(CASE WHEN hm_start > FLOOR(last_pm_hm / 250) * 250 + 250 + 25 THEN 0 ELSE operating_h END) AS ontime_h
    FROM last_pm GROUP BY site
),
fails AS (
    SELECT site,
           SUM(CASE WHEN pm_overdue THEN 1 ELSE 0 END)     AS overdue_breakdowns,
           SUM(CASE WHEN NOT pm_overdue THEN 1 ELSE 0 END) AS ontime_breakdowns
    FROM events WHERE event_type = 'Breakdown' GROUP BY site
)
SELECT c.*, ROUND(100 * e.overdue_h / (e.overdue_h + e.ontime_h), 1) AS pct_hours_overdue,
       ROUND(1000.0 * f.ontime_breakdowns  / e.ontime_h, 2)          AS bd_per_1000h_on_schedule,
       ROUND(1000.0 * f.overdue_breakdowns / NULLIF(e.overdue_h, 0), 2) AS bd_per_1000h_overdue
FROM compliance c JOIN exposure e USING (site) JOIN fails f USING (site)
ORDER BY pm_compliance_pct;
