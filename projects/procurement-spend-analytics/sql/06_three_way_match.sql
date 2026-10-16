-- 06_three_way_match.sql
-- 3-way match: compare PO (price), goods receipt (quantity) and supplier invoice.
-- Every exception is listed with the amount that would be overpaid if not caught.
WITH m AS (
    SELECT i.invoice_no, p.po_line, p.supplier_name, p.category,
           p.unit_price_usd, p.qty_received, i.unit_price_invoiced, i.qty_invoiced,
           CASE
             WHEN i.qty_invoiced >= 2 * p.qty_received AND p.qty_received > 0 THEN 'Duplicate billing'
             WHEN i.qty_invoiced > p.qty_received                       THEN 'Billed for undelivered qty'
             WHEN i.unit_price_invoiced > p.unit_price_usd * 1.005      THEN 'Price above PO'
             ELSE 'Matched' END AS match_status,
           i.unit_price_invoiced * i.qty_invoiced - p.unit_price_usd * p.qty_received AS overbilled_usd
    FROM invoices i JOIN po p USING (po_line)
)
SELECT match_status,
       COUNT(*)                              AS invoices,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_invoices,
       ROUND(SUM(GREATEST(overbilled_usd, 0)), 0) AS overbilled_usd
FROM m
GROUP BY match_status
ORDER BY invoices DESC;
