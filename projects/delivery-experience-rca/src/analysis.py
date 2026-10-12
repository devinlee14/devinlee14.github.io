"""
Delivery Experience Root Cause Analysis (Olist, real data).

Questions
  1. How much do late deliveries hurt review scores?
  2. Is lateness the main driver, once other factors are controlled for?
  3. Where in the fulfilment chain does lateness come from (seller vs carrier),
     and which routes / sellers / periods concentrate it?

Run:  python src/get_data.py && python src/analysis.py
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[1]
D, O = ROOT / "data", ROOT / "outputs"
SITE = ROOT.parents[1] / "assets" / "data"
O.mkdir(exist_ok=True)

ts = ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
      "order_delivered_customer_date", "order_estimated_delivery_date"]
orders = pd.read_csv(D / "olist_orders_dataset.csv", parse_dates=ts)
items = pd.read_csv(D / "olist_order_items_dataset.csv", parse_dates=["shipping_limit_date"])
cust = pd.read_csv(D / "olist_customers_dataset.csv")
sellers = pd.read_csv(D / "olist_sellers_dataset.csv")
reviews = pd.read_csv(D / "olist_order_reviews_dataset.csv").groupby("order_id").review_score.mean()
products = pd.read_csv(D / "olist_products_dataset.csv")
trans = pd.read_csv(D / "product_category_name_translation.csv")

# ------------------------------------------------------------ build order table
o = orders[(orders.order_status == "delivered")
           & orders.order_delivered_customer_date.notna()
           & orders.order_purchase_timestamp.between("2017-01-01", "2018-08-31")].copy()
o = o.merge(cust[["customer_id", "customer_state"]], on="customer_id")

it = items.merge(sellers[["seller_id", "seller_state"]], on="seller_id") \
          .merge(products[["product_id", "product_category_name", "product_weight_g"]], on="product_id", how="left") \
          .merge(trans, on="product_category_name", how="left")
agg = it.groupby("order_id").agg(n_items=("order_item_id", "count"), n_sellers=("seller_id", "nunique"),
                                 price=("price", "sum"), freight=("freight_value", "sum"),
                                 weight_kg=("product_weight_g", lambda s: s.sum() / 1000),
                                 seller_id=("seller_id", "first"), seller_state=("seller_state", "first"),
                                 shipping_limit=("shipping_limit_date", "max"),
                                 category=("product_category_name_english", "first"))
o = o.merge(agg, on="order_id").merge(reviews.rename("review_score"), on="order_id", how="left")

day = pd.Timedelta(days=1)
o["days_late"] = (o.order_delivered_customer_date - o.order_estimated_delivery_date) / day
o["late"] = o.days_late > 0
o["delivery_days"] = (o.order_delivered_customer_date - o.order_purchase_timestamp) / day
o["promised_days"] = (o.order_estimated_delivery_date - o.order_purchase_timestamp) / day
o["approval_days"] = (o.order_approved_at - o.order_purchase_timestamp) / day
o["seller_days"] = (o.order_delivered_carrier_date - o.order_approved_at) / day     # seller handling
o["carrier_days"] = (o.order_delivered_customer_date - o.order_delivered_carrier_date) / day
o["seller_missed_handover"] = o.order_delivered_carrier_date > o.shipping_limit
o["interstate"] = o.seller_state != o.customer_state
o["freight_ratio"] = o.freight / o.price
o["bad_review"] = o.review_score <= 2
o["month"] = o.order_purchase_timestamp.dt.to_period("M").astype(str)
o = o[(o.delivery_days > 0) & (o.carrier_days >= 0) & (o.seller_days >= 0)]   # drop corrupt timestamps
o.to_csv(O / "delivered_orders_model_table.csv.gz", index=False)

# ------------------------------------------------------------ 1. impact on reviews
bins = [-np.inf, 0, 3, 7, 14, np.inf]
labels = ["On time", "1-3 days late", "4-7 days late", "8-14 days late", "15+ days late"]
o["late_bucket"] = pd.cut(o.days_late, bins=bins, labels=labels)
impact = o.groupby("late_bucket", observed=True).agg(
    orders=("order_id", "count"), avg_review=("review_score", "mean"),
    bad_review_pct=("bad_review", "mean")).reset_index()
impact["bad_review_pct"] = (impact.bad_review_pct * 100).round(1)
impact["avg_review"] = impact.avg_review.round(2)
impact.to_csv(O / "01_review_by_lateness.csv", index=False)

# ------------------------------------------------------------ 2. logistic regression
m = o.dropna(subset=["review_score", "freight_ratio", "weight_kg"]).copy()
m["multi_seller"] = m.n_sellers > 1
m["log_promised"] = np.log1p(m.promised_days)
m["log_price"] = np.log1p(m.price)
model = smf.logit("bad_review ~ late + log_promised + multi_seller + n_items + interstate"
                  " + freight_ratio + log_price", data=m.astype({"bad_review": int})).fit(disp=0)
orr = pd.DataFrame({"odds_ratio": np.exp(model.params), "ci_low": np.exp(model.conf_int()[0]),
                    "ci_high": np.exp(model.conf_int()[1]), "p_value": model.pvalues}).drop("Intercept")
orr.index = orr.index.str.replace("[T.True]", "", regex=False)
orr = orr.round(3).sort_values("odds_ratio", ascending=False)
orr.to_csv(O / "02_logit_odds_ratios.csv")
(O / "02_logit_summary.txt").write_text(model.summary().as_text())

# ------------------------------------------------------------ 3. root cause of lateness
stage = o.groupby("late")[["approval_days", "seller_days", "carrier_days", "promised_days"]].median().round(1)
stage.to_csv(O / "03_stage_medians.csv")

late = o[o.late]
handover_late_share = late.seller_missed_handover.mean()
handover_ontime_share = o[~o.late].seller_missed_handover.mean()
late_if_missed = o[o.seller_missed_handover].late.mean()
late_if_ok = o[~o.seller_missed_handover].late.mean()

monthly = o.groupby("month").agg(orders=("order_id", "count"), late_rate=("late", "mean")).reset_index()
monthly["late_rate"] = (monthly.late_rate * 100).round(1)
monthly.to_csv(O / "04_late_rate_by_month.csv", index=False)

state = o.groupby("customer_state").agg(orders=("order_id", "count"), late_rate=("late", "mean"),
                                        avg_delivery_days=("delivery_days", "mean")).reset_index()
state = state[state.orders >= 300]
state["late_rate"] = (state.late_rate * 100).round(1)
state = state.sort_values("late_rate", ascending=False)
state.to_csv(O / "05_late_rate_by_customer_state.csv", index=False)

route = o.assign(route=np.where(o.interstate, "Interstate", "Same state")) \
         .groupby("route").agg(orders=("order_id", "count"), late_rate=("late", "mean"),
                               carrier_days=("carrier_days", "median")).reset_index()

sel = o.groupby("seller_id").agg(orders=("order_id", "count"), late_orders=("late", "sum")) \
       .sort_values("late_orders", ascending=False)
sel["cum_late_share"] = sel.late_orders.cumsum() / sel.late_orders.sum()
n_sellers = len(sel)
top_n = int((sel.cum_late_share <= 0.5).sum()) + 1
sel.head(50).to_csv(O / "06_top_sellers_by_late_orders.csv")

# ------------------------------------------------------------ impact sizing
ontime_bad = o[~o.late].bad_review.mean()
excess_bad = int(late.bad_review.sum() - len(late) * ontime_bad)
bad_from_late = excess_bad / o.bad_review.sum()

early_days = -o[~o.late].days_late.median()

summary = {
    "kpi": {
        "orders": len(o), "late_rate": round(o.late.mean() * 100, 1),
        "avg_review_ontime": round(o[~o.late].review_score.mean(), 2),
        "avg_review_late": round(late.review_score.mean(), 2),
        "bad_ontime": round(ontime_bad * 100, 1), "bad_late": round(late.bad_review.mean() * 100, 1),
        "late_odds_ratio": float(orr.loc["late", "odds_ratio"]),
        "excess_bad_reviews": excess_bad, "share_bad_from_late": round(bad_from_late * 100, 1),
        "late_if_missed_handover": round(late_if_missed * 100, 1),
        "late_if_handover_ok": round(late_if_ok * 100, 1),
        "missed_handover_share_of_late": round(handover_late_share * 100, 1),
        "median_early_days": round(early_days, 1),
        "top_sellers_for_half_late": top_n, "n_sellers": n_sellers,
        "top_sellers_pct": round(top_n / n_sellers * 100, 1),
        "worst_month": monthly.loc[monthly.late_rate.idxmax(), "month"],
        "worst_month_rate": float(monthly.late_rate.max()),
    },
    "impact": impact.astype({"late_bucket": str}).to_dict("records"),
    "odds": orr.reset_index().rename(columns={"index": "factor"}).to_dict("records"),
    "stage": {"labels": ["Approval", "Seller handling", "Carrier transit"],
              "on_time": stage.loc[False, ["approval_days", "seller_days", "carrier_days"]].tolist(),
              "late": stage.loc[True, ["approval_days", "seller_days", "carrier_days"]].tolist()},
    "monthly": monthly.to_dict("list"),
    "state": state.head(12).to_dict("list"),
    "route": route.round(3).to_dict("records"),
}
(O / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
(SITE / "delivery.json").write_text(json.dumps(summary, indent=1, default=str))
print(impact.to_string(index=False))
print(orr.to_string())
print(stage.to_string())
print(route.to_string())
print(json.dumps(summary["kpi"], indent=1, default=str))
