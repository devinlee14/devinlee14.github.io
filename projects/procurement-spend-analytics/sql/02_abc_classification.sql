-- 02_abc_classification.sql
-- ABC (Pareto) classification of part numbers by 2-year spend.
--   A = parts making up the first 80% of spend, B = next 15%, C = last 5%
WITH part_spend AS (
    SELECT part_no, category, critical, SUM(po_value) AS spend
    FROM po GROUP BY ALL
),
ranked AS (
    SELECT *,
           SUM(spend) OVER (ORDER BY spend DESC ROWS UNBOUNDED PRECEDING) / SUM(spend) OVER () AS cum_share,
           ROW_NUMBER() OVER (ORDER BY spend DESC) AS rank
    FROM part_spend
)
SELECT part_no, category, critical, ROUND(spend, 0) AS spend_usd, rank,
       ROUND(100 * cum_share, 2) AS cum_pct,
       CASE WHEN cum_share - spend / SUM(spend) OVER () < 0.80 THEN 'A'
            WHEN cum_share - spend / SUM(spend) OVER () < 0.95 THEN 'B'
            ELSE 'C' END AS abc_class
FROM ranked
ORDER BY rank;
