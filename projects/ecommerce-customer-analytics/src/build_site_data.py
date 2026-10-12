"""Summarise SQL outputs into JSON for the portfolio page (+ a significance test)."""
from pathlib import Path
import json
import duckdb
import pandas as pd
from statsmodels.stats.proportion import proportions_ztest

ROOT = Path(__file__).resolve().parents[1]
O = ROOT / "outputs"
SITE = ROOT.parents[1] / "assets" / "data"

con = duckdb.connect()
con.execute(f"SET file_search_path = '{ROOT}'")
con.execute((ROOT / "sql" / "00_staging.sql").read_text())
tot = con.sql("""SELECT COUNT(DISTINCT customer_id) customers, COUNT(*) orders, SUM(order_value) gmv,
                 (SELECT COUNT(*) FROM (SELECT customer_id FROM orders GROUP BY 1 HAVING COUNT(*)>1)) repeaters
                 FROM order_value""").df().iloc[0]

kpi = pd.read_csv(O / "01_monthly_kpis.csv")
coh = pd.read_csv(O / "02_cohort_retention.csv")
rfm = pd.read_csv(O / "03_rfm_segmentation.csv")
cat = pd.read_csv(O / "04_category_pareto.csv")
rep = pd.read_csv(O / "05_repeat_drivers.csv")

d = rep[rep.dimension == "delivery"].set_index("value")
counts = [round(d.loc[v, "customers"] * d.loc[v, "repeat_rate_pct"] / 100) for v in ["on time", "late"]]
z, p = proportions_ztest(counts, [d.loc["on time", "customers"], d.loc["late", "customers"]],
                         alternative="larger")

h1_17 = kpi[kpi.month.between("2017-01", "2017-06")].gmv.sum()
h1_18 = kpi[kpi.month.between("2018-01", "2018-06")].gmv.sum()

cohorts = sorted(coh.cohort.unique())[:12]
grid = [[float(coh[(coh.cohort == c) & (coh.month_number == m)].retention_pct.sum()) for m in range(1, 7)]
        for c in cohorts]

data = {
    "kpi": {"orders": int(tot.orders), "customers": int(tot.customers), "gmv": round(float(tot.gmv)),
            "repeat_rate": round(100 * tot.repeaters / tot.customers, 2),
            "h1_growth": round(100 * (h1_18 / h1_17 - 1), 0),
            "black_friday_mom": float(kpi.set_index("month").loc["2017-11", "gmv_mom_pct"]),
            "top10_share": float(cat.iloc[9].cumulative_pct), "categories": len(cat),
            "late_repeat": float(d.loc["late", "repeat_rate_pct"]),
            "ontime_repeat": float(d.loc["on time", "repeat_rate_pct"]), "p_value": float(p)},
    "monthly": {"months": kpi.month.tolist(), "gmv": kpi.gmv.tolist(), "orders": kpi.orders.tolist(),
                "aov": kpi.aov.tolist()},
    "cohort": {"cohorts": cohorts, "months": list(range(1, 7)), "grid": grid,
               "sizes": [int(coh[(coh.cohort == c) & (coh.month_number == 0)].customers.iloc[0]) for c in cohorts]},
    "rfm": rfm[["segment", "customers", "pct_customers", "pct_revenue", "avg_monetary"]].to_dict("records"),
    "pareto": {"labels": cat.category.head(15).str.replace("_", " ").tolist(),
               "revenue": cat.revenue.head(15).tolist(), "cum": cat.cumulative_pct.head(15).tolist()},
    "repeat": rep.to_dict("records"),
}
(SITE / "ecommerce.json").write_text(json.dumps(data, indent=1))
print(json.dumps(data["kpi"], indent=1))
