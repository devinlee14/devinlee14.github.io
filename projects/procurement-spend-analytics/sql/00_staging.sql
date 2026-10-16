-- 00_staging.sql : analysis-ready views on top of the ERP extracts
CREATE OR REPLACE VIEW suppliers AS SELECT * FROM read_csv_auto('data/suppliers.csv');
CREATE OR REPLACE VIEW parts     AS SELECT * FROM read_csv_auto('data/parts.csv');
CREATE OR REPLACE VIEW invoices  AS SELECT * FROM read_csv_auto('data/invoices.csv');

CREATE OR REPLACE VIEW po AS
SELECT o.*,
       p.category, p.critical, p.contract_supplier,
       s.supplier_name, s.supplier_type,
       o.unit_price_usd * o.qty_ordered                                   AS po_value,
       o.supplier_id <> p.contract_supplier                               AS off_contract,
       -- contract price for the year of the order (2025 contracts +4.5%)
       p.contract_price_2024 * CASE WHEN YEAR(o.pr_date) = 2025 THEN 1.045 ELSE 1 END AS contract_price,
       DATE_DIFF('day', o.pr_date, o.po_date)                             AS approval_days,
       DATE_DIFF('day', o.po_date, o.gr_date)                             AS lead_time_days,
       o.gr_date <= o.promised_date                                       AS on_time,
       o.qty_received >= o.qty_ordered                                    AS in_full
FROM read_csv_auto('data/purchase_orders.csv') o
JOIN parts p USING (part_no)
JOIN suppliers s USING (supplier_id);
