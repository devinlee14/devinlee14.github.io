# Delivery Experience Root Cause Analysis

**Why do customers leave 1–2 star reviews, and where does lateness come from? A root cause analysis of ~95k real delivered orders from the Olist marketplace.**

Dataset: [Olist Brazilian E-Commerce Public Dataset](https://github.com/olist/work-at-olist-data) (real, anonymised, CC BY-NC-SA 4.0). Scope: delivered orders purchased Jan 2017 – Aug 2018.

## Business problem
Review scores drive marketplace ranking and repeat purchases. The question: **how much does delivery performance drive bad reviews, and which part of the fulfilment chain should operations fix first?**

## Approach (`src/analysis.py`)
1. **Build an order-level table:** join orders, items, sellers, customers, products and reviews. Derive timestamps for each fulfilment stage: approval → seller handling → carrier transit. Drop records with corrupt timestamps.
2. **Measure impact:** review score and % of 1–2★ reviews by lateness bucket.
3. **Isolate the driver:** logistic regression `P(1–2★ review)` controlling for promised lead time, number of items, multi-seller orders, interstate shipping, freight ratio and price. Report odds ratios with 95% confidence intervals.
4. **Root cause:** compare median stage durations for late vs on-time orders. Check whether the seller missed the carrier handover deadline. Break down late rate by month, customer state and route; test whether a few sellers concentrate lateness.
5. **Size the impact:** estimate excess bad reviews caused by lateness (late orders vs the on-time baseline).

## Key findings
- **8.2%** of orders arrived late. Average review drops from **4.29★ to 2.56★**, and 1–2★ reviews rise from **9.1% to 52.9%**. At 4+ days late, the majority of reviews are 1–2★.
- **Lateness is the strongest driver:** controlling for other factors, a late order has **13.9× the odds** of a 1–2★ review (95% CI 13.2–14.7). Orders split across **multiple sellers** come next (5.0×).
- **~3,400 bad reviews (28% of all 1–2★ reviews)** are attributable to late delivery.
- **The delay happens mostly in carrier transit:** late orders spend a median **23.9 days** with the carrier vs **6.9** for on-time orders. Seller handling also slips (3.0 vs 1.8 days). When the seller misses the handover deadline, the late rate jumps from **6.6% to 24.8%**, but 73% of late orders were handed over on time.
- **Lateness is systemic and seasonal, not driven by a few bad sellers:** late rate spiked to **14.3%** around Black Friday (Nov 2017) and **16–21%** in Feb–Mar 2018, vs 3–5% in normal months. The sellers with the most late orders are simply the biggest sellers (their late rate is 9.6% vs the 8.2% average).
- **Delivery promises are very conservative:** the median on-time order arrives **12.3 days early**. Yet when a delay happens, it blows past even that buffer.

## Recommendations
1. **Plan carrier capacity for peaks:** pre-book capacity and add backup carriers ahead of Black Friday and Q1. This is where most late orders come from.
2. **Set up a seller handover SLA alert:** flag orders not handed over by `shipping_limit_date` and nudge sellers. Late risk is 3.8× higher when the handover deadline is missed.
3. **Contact customers proactively** when an order crosses its estimated date (apology + voucher), targeting the 4+ days-late group where most reviews turn 1–2★.
4. **Consolidate multi-seller orders** or set expectations for split shipments.
5. **Re-calibrate delivery estimates** per route. Over-padding by 12 days may cost conversions without protecting the customer when real delays happen.

## Outputs
`outputs/01_review_by_lateness.csv`, `02_logit_odds_ratios.csv` (+ full model summary), `03_stage_medians.csv`, `04_late_rate_by_month.csv`, `05_late_rate_by_customer_state.csv`, `06_top_sellers_by_late_orders.csv`

## Tools
Python (pandas, NumPy, statsmodels) · logistic regression · root cause analysis · process-stage decomposition
