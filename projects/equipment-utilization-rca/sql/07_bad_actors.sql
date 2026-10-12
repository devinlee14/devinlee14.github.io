-- 07_bad_actors.sql
-- Top 10 "bad actor" units by unplanned downtime, ranked within the fleet.
WITH u AS (
    SELECT unit_id, site, model, COUNT(*) AS breakdowns, ROUND(SUM(duration_h), 0) AS downtime_h
    FROM events WHERE event_type = 'Breakdown' GROUP BY ALL
)
SELECT DENSE_RANK() OVER (ORDER BY downtime_h DESC) AS rank, u.*,
       un.commission_year,
       ROUND(100.0 * downtime_h / SUM(downtime_h) OVER (), 1) AS pct_of_fleet_downtime
FROM u JOIN units un USING (unit_id, site, model)
QUALIFY rank <= 10
ORDER BY rank;
