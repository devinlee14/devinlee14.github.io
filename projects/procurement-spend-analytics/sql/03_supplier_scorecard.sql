-- 03_supplier_scorecard.sql
-- Supplier performance: OTIF, lead time and its variability, quality and price.
-- Price index compares what we paid with the contract price for the same part,
-- on planned (non-urgent) lines only so expediting does not distort it.
WITH base AS (
    SELECT supplier_id, supplier_name, supplier_type,
           COUNT(*)                                                      AS po_lines,
           SUM(po_value)                                                 AS spend,
           AVG(CASE WHEN on_time AND in_full THEN 1 ELSE 0 END)          AS otif,
           AVG(lead_time_days)                                           AS avg_lead_time,
           STDDEV_SAMP(lead_time_days)                                   AS sd_lead_time,
           SUM(qty_rejected) / NULLIF(SUM(qty_received), 0)              AS reject_rate,
           AVG(CASE WHEN NOT urgent THEN unit_price_usd / contract_price END) AS price_vs_contract
    FROM po GROUP BY ALL
)
SELECT supplier_id, supplier_name, supplier_type, po_lines,
       ROUND(spend, 0)                     AS spend_usd,
       ROUND(100 * otif, 1)                AS otif_pct,
       ROUND(avg_lead_time, 1)             AS avg_lead_time_days,
       ROUND(sd_lead_time, 1)              AS sd_lead_time_days,
       ROUND(100 * reject_rate, 2)         AS reject_pct,
       ROUND(price_vs_contract, 3)         AS price_vs_contract,
       -- composite score (0-100): delivery 40, quality 30, lead-time reliability 30
       ROUND(40 * otif
           + 30 * GREATEST(0, 1 - reject_rate / 0.06)
           + 30 * GREATEST(0, 1 - sd_lead_time / 12), 1) AS score
FROM base
ORDER BY score DESC;
