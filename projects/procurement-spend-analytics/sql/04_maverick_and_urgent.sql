-- 04_maverick_and_urgent.sql
-- Off-contract ("maverick") and urgent buying: how common, and what it costs.
-- Premium = price paid above the contract price, plus expedite (air freight) charges.
SELECT site,
       COUNT(*)                                                         AS po_lines,
       ROUND(100 * AVG(CASE WHEN urgent THEN 1 ELSE 0 END), 1)          AS urgent_pct,
       ROUND(100 * AVG(CASE WHEN off_contract THEN 1 ELSE 0 END), 1)    AS off_contract_pct,
       ROUND(SUM(GREATEST(unit_price_usd - contract_price, 0) * qty_ordered), 0) AS price_premium_usd,
       ROUND(SUM(expedite_cost_usd), 0)                                 AS expedite_usd,
       ROUND(SUM(GREATEST(unit_price_usd - contract_price, 0) * qty_ordered) + SUM(expedite_cost_usd), 0) AS total_premium_usd
FROM po
GROUP BY site
ORDER BY total_premium_usd DESC;
