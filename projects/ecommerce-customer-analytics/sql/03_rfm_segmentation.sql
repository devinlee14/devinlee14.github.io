-- 03_rfm_segmentation.sql
-- RFM segmentation. ~97% of customers buy only once, so NTILE() on frequency
-- would be meaningless; frequency is scored with business thresholds instead,
-- while recency and monetary use quintiles.
-- Techniques: NTILE window function, CASE-based scoring, segment rules.
WITH base AS (
    SELECT customer_id,
           DATE_DIFF('day', MAX(purchased_at), TIMESTAMP '2018-09-01') AS recency_days,
           COUNT(*)                                                    AS frequency,
           SUM(order_value)                                            AS monetary
    FROM order_value
    GROUP BY customer_id
),
scored AS (
    SELECT *,
           6 - NTILE(5) OVER (ORDER BY recency_days) AS r_score,   -- 5 = most recent
           CASE WHEN frequency >= 3 THEN 5 WHEN frequency = 2 THEN 4 ELSE 1 END AS f_score,
           NTILE(5) OVER (ORDER BY monetary)         AS m_score
    FROM base
),
segmented AS (
    SELECT *,
           CASE
             WHEN f_score >= 4 AND r_score >= 4                  THEN 'Champions'
             WHEN f_score >= 4                                   THEN 'Loyal - at risk'
             WHEN r_score >= 4 AND m_score >= 4                  THEN 'New high-value'
             WHEN r_score >= 4                                   THEN 'New low-value'
             WHEN r_score = 3                                    THEN 'Cooling down'
             WHEN m_score >= 4                                   THEN 'Lost high-value'
             ELSE 'Lost low-value'
           END AS segment
    FROM scored
)
SELECT segment,
       COUNT(*)                                   AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_customers,
       ROUND(SUM(monetary), 0)                    AS revenue,
       ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 1) AS pct_revenue,
       ROUND(AVG(recency_days), 0)                AS avg_recency_days,
       ROUND(AVG(frequency), 2)                   AS avg_frequency,
       ROUND(AVG(monetary), 2)                    AS avg_monetary
FROM segmented
GROUP BY segment
ORDER BY revenue DESC;
