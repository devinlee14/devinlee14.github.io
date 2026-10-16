-- 01_spend_overview.sql
-- Where does the money go? Spend by category and supplier type, with share of total.
SELECT category,
       supplier_type,
       COUNT(*)                                                    AS po_lines,
       ROUND(SUM(po_value), 0)                                     AS spend_usd,
       ROUND(100 * SUM(po_value) / SUM(SUM(po_value)) OVER (), 1)  AS pct_of_total
FROM po
GROUP BY ALL
ORDER BY spend_usd DESC;
