"""Export compact JSON used by the portfolio web page charts."""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
SITE = ROOT.parents[1] / "assets" / "data"
SITE.mkdir(parents=True, exist_ok=True)

clean = pd.read_csv(OUT / "clean_consumption.csv")
issues = pd.read_csv(OUT / "issue_log.csv")
changes = pd.read_csv(OUT / "change_log.csv")
em = pd.read_csv(OUT / "emissions_monthly.csv")
gap = pd.read_csv(OUT / "invoice_gap_report.csv")
ev = json.loads((OUT / "evaluation.json").read_text())
raw = pd.read_csv(ROOT / "data" / "portal_submissions.csv")

monthly = em.pivot_table(index="period", columns="scope", values="tco2e", aggfunc="sum").round(1)
orn = clean.drop_duplicates(["property_id", "period"]).groupby("country").occupied_room_nights.sum()
by_country = (em.groupby("country").tco2e.sum() * 1000 / orn).sort_values().round(1)

leak = clean[(clean.property_id == "HTL-017") & (clean.utility == "water")].sort_values("period")

rec = pd.DataFrame(ev["recall_by_error"])
labels = {"bill_mismatch": "Mismatch vs bill", "decimal_shift": "Decimal shift (x10)",
          "duplicate_conflicting": "Conflicting duplicate", "duplicate_exact": "Exact duplicate",
          "missing": "Missing submission", "unit_mislabel": "Unit mislabel (MWh as kWh)",
          "zero_or_negative": "Zero / negative value"}

std_changes = changes[changes.field.isin(["property_id", "period"]) |
                      changes.reason.str.startswith("unit conversion")]
data = {
    "kpi": {
        "properties": int(clean.property_id.nunique()),
        "countries": int(clean.country.nunique()),
        "raw_rows": len(raw),
        "records": len(clean),
        "issues": len(issues),
        "auto_standardised": len(std_changes),
        "recall": ev["overall_recall_pct"],
        "false_alarms": ev["false_alarm_changes"],
        "within2_before": ev["before"]["records_within_2pct"],
        "within2_after": ev["after"]["records_within_2pct"],
        "missing_before": ev["before"]["missing_records"],
        "invoices_to_chase": len(gap),
        "total_tco2e": round(em.tco2e.sum()),
    },
    "recall": [{"label": labels[r.error_injected], "caught": int(r["sum"]), "total": int(r["count"])}
               for _, r in rec.sort_values("count", ascending=False).iterrows()],
    "status": clean.data_status.value_counts().to_dict(),
    "monthly": {"periods": monthly.index.tolist(),
                "scope2": monthly["Scope 2"].tolist(), "scope1": monthly["Scope 1"].tolist()},
    "intensity_by_country": {"labels": by_country.index.tolist(), "values": by_country.tolist()},
    "leak": {"periods": leak.period.tolist(), "values": leak.value.round(0).tolist()},
    "issue_sample": issues[issues.rule.isin(["unit_mislabel", "decimal_shift", "bill_mismatch",
                                             "duplicate_conflicting", "intensity_outlier"])]
                    .groupby("rule").head(1)[["issue_id", "property_id", "period", "utility",
                                              "rule", "detail", "action"]].to_dict("records"),
}
(SITE / "hotel-esg.json").write_text(json.dumps(data, indent=1))
print(json.dumps(data["kpi"], indent=1))
