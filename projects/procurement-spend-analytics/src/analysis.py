"""
Savings sizing and safety-stock recommendations, built on the SQL outputs.

  1. Savings opportunities (annualised):
       a. planned off-contract buying -> premium over contract price is fully avoidable
       b. urgent orders -> if every site reached the best site's urgent rate
       c. 3-way match -> overbilling that is caught before payment
  2. Reorder point and safety stock for critical A/B parts at a 95% service level:
       ROP = d * L + z * sqrt(L * sd_d^2 + d^2 * sd_L^2)
     where d = average daily usage, L = average lead time (days) of the contract supplier.
  3. JSON for the portfolio page.

Run (after run_analysis.py):  python src/analysis.py
"""
from pathlib import Path
import json
import duckdb
import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
O = ROOT / "outputs"
SITE = ROOT.parents[1] / "assets" / "data"
con = duckdb.connect()
con.execute(f"SET file_search_path = '{ROOT}'")
con.execute((ROOT / "sql" / "00_staging.sql").read_text())
YEARS = 2.0

po = con.sql("SELECT * FROM po").df()
total_spend = po.po_value.sum()

# ------------------------------------------------------------ 1a. planned off-contract
planned_off = po[po.off_contract & ~po.urgent]
off_premium = ((planned_off.unit_price_usd - planned_off.contract_price).clip(lower=0) * planned_off.qty_ordered).sum()

# ------------------------------------------------------------ 1b. urgent orders
urg = po[po.urgent]
urg_cost_per_line = (((urg.unit_price_usd - urg.contract_price).clip(lower=0) * urg.qty_ordered)
                     + urg.expedite_cost_usd).groupby(urg.site).sum() / urg.groupby("site").size()
site_rate = po.groupby("site").urgent.mean()
best_rate = site_rate.min()
best_site = site_rate.idxmin()
lines = po.groupby("site").size()
urgent_avoidable = sum(max(0, site_rate[s] - best_rate) * lines[s] * urg_cost_per_line[s] for s in site_rate.index)
urgent_total = (((urg.unit_price_usd - urg.contract_price).clip(lower=0) * urg.qty_ordered) + urg.expedite_cost_usd).sum()

# ------------------------------------------------------------ 1c. 3-way match
twm = pd.read_csv(O / "06_three_way_match.csv")
overbilled = twm.overbilled_usd.sum()
exceptions = int(twm[twm.match_status != "Matched"].invoices.sum())

savings = pd.DataFrame([
    ("Stop planned off-contract buying", off_premium / YEARS),
    (f"Cut urgent orders to best-site level ({best_rate:.0%})", urgent_avoidable / YEARS),
    ("Block overbilled invoices (3-way match)", overbilled / YEARS),
], columns=["lever", "usd_per_year"])
savings.to_csv(O / "07_savings_opportunities.csv", index=False)

# ------------------------------------------------------------ 2. safety stock
abc = pd.read_csv(O / "02_abc_classification.csv")
usage = pd.read_csv(ROOT / "data" / "daily_usage.csv", parse_dates=["date"])
parts = pd.read_csv(ROOT / "data" / "parts.csv")
crit_ab = abc[(abc.critical) & (abc.abc_class.isin(["A", "B"]))].part_no
days = pd.date_range("2025-01-01", "2025-12-31", freq="D")
rows = []
z = norm.ppf(0.95)
for pn in crit_ab:
    u = usage[usage.part_no == pn].set_index("date").qty_used.reindex(days, fill_value=0)
    d, sd_d = u.mean(), u.std()
    contract = parts.set_index("part_no").loc[pn, "contract_supplier"]
    lt = po[(po.part_no == pn) & (po.supplier_id == contract) & ~po.urgent].lead_time_days
    if len(lt) < 3:
        lt = po[(po.supplier_id == contract) & ~po.urgent].lead_time_days
    L, sd_L = lt.mean(), lt.std()
    sigma_dl = np.sqrt(L * sd_d ** 2 + d ** 2 * sd_L ** 2)
    ss = z * sigma_dl
    price = parts.set_index("part_no").loc[pn, "contract_price_2024"]
    rows.append(dict(part_no=pn, category=parts.set_index("part_no").loc[pn, "category"],
                     contract_supplier=contract, avg_daily_use=round(d, 2), sd_daily_use=round(sd_d, 2),
                     avg_lead_time=round(L, 1), sd_lead_time=round(sd_L, 1),
                     current_rop=round(d * L, 1), safety_stock=round(ss, 1), recommended_rop=round(d * L + ss, 1),
                     stockout_risk_now_pct=round(100 * (1 - norm.cdf(0)), 0), stockout_risk_new_pct=5,
                     ss_value_usd=round(ss * price, 0)))
ss = pd.DataFrame(rows).sort_values("ss_value_usd", ascending=False)
ss.to_csv(O / "08_safety_stock_critical_parts.csv", index=False)

# share of safety stock driven by lead-time variability (vs demand variability)
lt_share = float(np.mean([(r.avg_daily_use ** 2 * r.sd_lead_time ** 2) /
                          max(1e-9, r.avg_lead_time * r.sd_daily_use ** 2 + r.avg_daily_use ** 2 * r.sd_lead_time ** 2)
                          for r in ss.itertuples()]))

# ------------------------------------------------------------ 3. JSON for site
spend_cat = con.sql("SELECT category, supplier_type, SUM(po_value) v FROM po GROUP BY ALL").df()
cats = spend_cat.groupby("category").v.sum().sort_values(ascending=False).index.tolist()
types = ["OEM", "Authorised distributor", "Aftermarket"]
spend_matrix = {t: [round(float(spend_cat[(spend_cat.category == c) & (spend_cat.supplier_type == t)].v.sum()))
                    for c in cats] for t in types}
sc = pd.read_csv(O / "03_supplier_scorecard.csv")
mu = pd.read_csv(O / "04_maverick_and_urgent.csv")
ct = pd.read_csv(O / "05_cycle_time.csv")
a_share_parts = float((abc.abc_class == "A").mean())
pareto_pts = abc[["rank", "cum_pct"]].iloc[::4]
planned = ct[~ct.urgent]

data = {
    "kpi": {
        "spend": round(float(total_spend)), "po_lines": len(po), "suppliers": int(po.supplier_id.nunique()),
        "parts": int(po.part_no.nunique()),
        "a_parts_pct": round(100 * a_share_parts, 1), "a_parts_n": int((abc.abc_class == "A").sum()),
        "otif": round(100 * float((po.on_time & po.in_full).mean()), 1),
        "urgent_pct": round(100 * float(po.urgent.mean()), 1),
        "off_contract_pct": round(100 * float(po.off_contract.mean()), 1),
        "urgent_premium_total": round(float(urgent_total)),
        "premium_pct_spend": round(100 * float((urgent_total + off_premium) / total_spend), 1),
        "savings_per_year": round(float(savings.usd_per_year.sum())),
        "savings_pct": round(100 * float(savings.usd_per_year.sum() / (total_spend / YEARS)), 1),
        "exceptions": exceptions, "exceptions_pct": round(100 * exceptions / len(po), 1),
        "overbilled": round(float(overbilled)),
        "approval_small": float(planned[planned.value_band.isin(["1. up to $1k", "2. $1k-5k"])].median_approval_days.median()),
        "approval_big": float(planned[planned.value_band.isin(["3. $5k-20k", "4. above $20k"])].median_approval_days.median()),
        "best_site": best_site.split(" - ")[1], "best_rate": round(100 * best_rate, 1),
        "worst_site": site_rate.idxmax().split(" - ")[1], "worst_rate": round(100 * site_rate.max(), 1),
        "ss_parts": len(ss), "ss_value": round(float(ss.ss_value_usd.sum())),
        "lt_share": round(100 * lt_share),
    },
    "spend": {"categories": cats, "matrix": spend_matrix},
    "pareto": {"rank": pareto_pts["rank"].tolist(), "cum": pareto_pts.cum_pct.tolist(), "n": len(abc)},
    "suppliers": sc[["supplier_name", "supplier_type", "spend_usd", "otif_pct", "avg_lead_time_days",
                     "sd_lead_time_days", "reject_pct", "price_vs_contract", "score"]].to_dict("records"),
    "sites": mu.to_dict("records"),
    "cycle": ct.to_dict("records"),
    "match": twm.to_dict("records"),
    "savings": savings.round(0).to_dict("records"),
    "safety": ss.head(10)[["part_no", "category", "avg_daily_use", "avg_lead_time", "sd_lead_time",
                           "current_rop", "recommended_rop", "safety_stock", "ss_value_usd"]].to_dict("records"),
}
(SITE / "procurement.json").write_text(json.dumps(data, indent=1, default=float))
print(json.dumps(data["kpi"], indent=1))
print(savings.to_string(index=False))
print(ss.head(8).to_string(index=False))
