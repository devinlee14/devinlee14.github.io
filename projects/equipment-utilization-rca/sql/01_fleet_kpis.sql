-- 01_fleet_kpis.sql
-- Physical Availability (PA) and Use of Availability (UA) by site and month.
--   PA = (scheduled - downtime) / scheduled      -> is the machine ready?
--   UA = operating / (scheduled - downtime)      -> when ready, is it used?
SELECT site,
       STRFTIME(DATE_TRUNC('month', date), '%Y-%m')                         AS month,
       ROUND(100 * (1 - SUM(downtime_h) / SUM(scheduled_h)), 1)             AS pa_pct,
       ROUND(100 * SUM(operating_h) / (SUM(scheduled_h) - SUM(downtime_h)), 1) AS ua_pct,
       ROUND(100 * SUM(standby_weather_h) / SUM(scheduled_h), 1)            AS weather_standby_pct,
       ROUND(SUM(operating_h), 0)                                           AS operating_h
FROM daily
GROUP BY ALL
ORDER BY site, month;
