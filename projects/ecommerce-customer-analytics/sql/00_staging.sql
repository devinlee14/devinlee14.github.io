-- 00_staging.sql
-- Clean, analysis-ready views on top of the raw Olist CSVs.
-- Scope: purchases Jan-2017 to Aug-2018 (complete months only),
-- excluding canceled / unavailable orders.

CREATE OR REPLACE VIEW orders AS
SELECT o.order_id,
       c.customer_unique_id                       AS customer_id,   -- real person id (customer_id is per order)
       c.customer_state                           AS state,
       o.order_status,
       o.order_purchase_timestamp                 AS purchased_at,
       DATE_TRUNC('month', o.order_purchase_timestamp) AS order_month,
       o.order_delivered_customer_date            AS delivered_at,
       o.order_estimated_delivery_date            AS estimated_at
FROM read_csv_auto('data/olist_orders_dataset.csv')    o
JOIN read_csv_auto('data/olist_customers_dataset.csv') c USING (customer_id)
WHERE o.order_status NOT IN ('canceled', 'unavailable')
  AND o.order_purchase_timestamp >= '2017-01-01'
  AND o.order_purchase_timestamp <  '2018-09-01';

CREATE OR REPLACE VIEW items AS
SELECT i.order_id, i.order_item_id, i.product_id, i.seller_id,
       i.price, i.freight_value,
       COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category
FROM read_csv_auto('data/olist_order_items_dataset.csv') i
LEFT JOIN read_csv_auto('data/olist_products_dataset.csv') p USING (product_id)
LEFT JOIN read_csv_auto('data/product_category_name_translation.csv') t USING (product_category_name);

-- one row per order with its value (product price + freight)
CREATE OR REPLACE VIEW order_value AS
SELECT o.*, v.n_items, v.product_value, v.freight_value, v.product_value + v.freight_value AS order_value
FROM orders o
JOIN (SELECT order_id, COUNT(*) AS n_items, SUM(price) AS product_value, SUM(freight_value) AS freight_value
      FROM items GROUP BY order_id) v USING (order_id);

CREATE OR REPLACE VIEW reviews AS
SELECT order_id, AVG(review_score) AS review_score          -- a few orders have >1 review
FROM read_csv_auto('data/olist_order_reviews_dataset.csv')
GROUP BY order_id;
