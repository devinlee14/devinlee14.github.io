-- 05_cycle_time.sql
-- Procure-to-receive cycle: requisition -> PO approval -> goods receipt,
-- split by PO value band (POs above USD 5,000 need a second approval).
SELECT CASE WHEN po_value <= 1000 THEN '1. up to $1k'
            WHEN po_value <= 5000 THEN '2. $1k-5k'
            WHEN po_value <= 20000 THEN '3. $5k-20k'
            ELSE '4. above $20k' END                      AS value_band,
       urgent,
       COUNT(*)                                           AS po_lines,
       ROUND(MEDIAN(approval_days), 1)                    AS median_approval_days,
       ROUND(QUANTILE_CONT(approval_days, 0.9), 1)        AS p90_approval_days,
       ROUND(MEDIAN(lead_time_days), 1)                   AS median_lead_time_days
FROM po
GROUP BY ALL
ORDER BY value_band, urgent;
