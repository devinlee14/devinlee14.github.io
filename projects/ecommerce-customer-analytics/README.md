# E-Commerce Growth & Customer Retention Analysis (SQL)

**SQL analysis of ~98k real orders from Olist, a Brazilian marketplace: growth KPIs, cohort retention, RFM segmentation, category Pareto, and what makes customers come back.**

Dataset: [Brazilian E-Commerce Public Dataset by Olist](https://github.com/olist/work-at-olist-data) (real, anonymised, CC BY-NC-SA 4.0). Scope: Jan 2017 – Aug 2018, excluding canceled and unavailable orders. Values are in Brazilian reais (R$).

## Business questions
1. How fast is the marketplace growing, and what drives the peaks?
2. Do customers come back after their first purchase?
3. Which customer segments hold the revenue, and who should marketing target?
4. Which categories matter most?
5. Does the first-order experience (delivery, review) affect repeat purchases?

## Approach
| File | What it does | SQL techniques |
|---|---|---|
| `00_staging.sql` | clean views; join customers on `customer_unique_id` (the real person) instead of the per-order `customer_id` | joins, views, filtering |
| `01_monthly_kpis.sql` | GMV, orders, AOV, MoM growth, 3-month rolling average | `LAG`, rolling `AVG() OVER` |
| `02_cohort_retention.sql` | monthly acquisition cohorts, retention M+1 … M+12 | CTEs, `MIN() OVER (PARTITION BY)`, `DATE_DIFF` |
| `03_rfm_segmentation.sql` | RFM scoring and 7 actionable segments | `NTILE`, `CASE` scoring, share-of-total windows |
| `04_category_pareto.sql` | revenue concentration by category | running `SUM() OVER`, `ROW_NUMBER` |
| `05_repeat_drivers.sql` | repeat rate by first-order delivery outcome and review score | `ROW_NUMBER` to isolate first orders |
| `06_state_performance.sql` | GMV, AOV, freight burden by state | aggregation |

Run with DuckDB: `python src/get_data.py && python src/run_analysis.py`

## Key findings
- **Strong growth:** GMV in H1 2018 was **+181%** vs H1 2017. Black Friday (Nov 2017) lifted GMV **+53% MoM**.
- **Retention is the biggest gap:** only **3.0%** of 94.7k customers ever placed a second order, and every cohort's month-1 retention is below 1%. Growth comes almost entirely from new customers.
- **Revenue sits with one-time high-value buyers:** "New high-value" (15% of customers) and "Lost high-value" (15%) together bring **56% of revenue**. Repeat customers (Champions + Loyal) are only 3% of customers.
- **Long-tail categories:** the top 10 of 74 categories account for 62% of revenue. Health & beauty, watches & gifts and bed & bath lead.
- **Delivery affects loyalty:** customers whose first order arrived **late** came back at **3.19%** vs **4.09%** when on time, **22% lower** (two-proportion z-test, p = 0.002).

## Recommendations
1. **Launch a second-purchase program** for the "New high-value" segment (e.g. a timed voucher 30–45 days after delivery). Lifting repeat rate from 3% to 5% would add roughly 1.9k repeat customers per 95k acquired.
2. **Win back "Lost high-value" customers** (13.9k people, avg R$309 per customer) with category-specific campaigns.
3. **Treat on-time delivery as a retention lever, not just an ops KPI.** See the companion project *Delivery Experience Root Cause Analysis*.
4. **Plan inventory, logistics and customer service capacity for Black Friday**, which is the single biggest demand spike.

## Tools
SQL (DuckDB) · Python (pandas, statsmodels) · cohort analysis · RFM · hypothesis testing
