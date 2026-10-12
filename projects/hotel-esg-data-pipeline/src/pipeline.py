"""
Hotel utility data pipeline: standardise -> validate -> reconcile -> gap-fill
-> calculate emissions, with a full audit trail.

Inputs (data/):
  properties.csv, occupancy.csv, portal_submissions.csv, utility_bills.csv
Outputs (outputs/):
  clean_consumption.csv   one row per property-month-utility with a data_status
  issue_log.csv           every issue found, the rule that found it and the action taken
  change_log.csv          every value that was changed (old -> new, reason, source)
  invoice_gap_report.csv  expected vs received utility bills (to chase providers)
  property_scorecard.csv  data quality score per property
  emissions_monthly.csv   Scope 2 (electricity) + Scope 1 (gas) emissions

Run:  python src/pipeline.py
"""
from pathlib import Path
import re
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "outputs"
OUT.mkdir(exist_ok=True)

TOLERANCE = 0.02          # submitted vs bill: accepted difference
MAD_Z_LIMIT = 6.0         # robust z-score limit (conservative, avoids alert fatigue)
MAD_Z_REJECT = 15.0       # beyond this and no bill to confirm -> physically implausible
KEY = ["property_id", "period", "utility"]

# Illustrative emission factors (kgCO2e per kWh). They approximate published
# national grid averages and are for demonstration only; a real engagement
# would use the client-approved factor set for each reporting year.
GRID_EF = {"Singapore": 0.41, "Indonesia": 0.79, "Thailand": 0.47, "Malaysia": 0.67,
           "Vietnam": 0.68, "Japan": 0.45, "Australia": 0.66, "United Arab Emirates": 0.42}
GAS_EF = 0.183            # natural gas, kgCO2e per kWh (illustrative)

issues, changes = [], []


def log_issue(row, rule, severity, detail, action):
    issues.append(dict(property_id=row["property_id"], period=row["period"], utility=row["utility"],
                       rule=rule, severity=severity, detail=detail, action=action))


def log_change(row, field, old, new, reason, source):
    changes.append(dict(property_id=row["property_id"], period=row["period"], utility=row["utility"],
                        field=field, old_value=old, new_value=new, reason=reason, source=source))


# ------------------------------------------------------------------ load
props = pd.read_csv(DATA / "properties.csv")
occ = pd.read_csv(DATA / "occupancy.csv")
raw = pd.read_csv(DATA / "portal_submissions.csv", dtype={"property_id": str, "period": str})
bills = pd.read_csv(DATA / "utility_bills.csv", parse_dates=["billing_start", "billing_end"])
valid_ids = set(props.property_id)
n_raw = len(raw)

# ------------------------------------------------- 1. standardise
df = raw.copy()


def clean_id(x):
    m = re.search(r"HTL-?(\d+)", str(x).strip().upper())
    return f"HTL-{int(m.group(1)):03d}" if m else str(x).strip()


def clean_period(x):
    return pd.Period(pd.to_datetime(str(x).replace("/", "-"), format="mixed"), "M").strftime("%Y-%m")


for col, fn in [("property_id", clean_id), ("period", clean_period)]:
    new = df[col].map(fn)
    for i in df.index[new != df[col]]:
        row = df.loc[i].copy()
        row[col] = new[i]
        log_change(row, col, df.at[i, col], new[i], f"non-standard {col} format", "rule")
    df[col] = new

unknown = df[~df.property_id.isin(valid_ids)]
for _, r in unknown.iterrows():
    log_issue(r, "unknown_property", "high", "ID not in property master", "quarantined")
df = df[df.property_id.isin(valid_ids)]

UNIT_FACTOR = {("electricity", "KWH"): 1, ("electricity", "MWH"): 1000, ("gas", "KWH"): 1,
               ("water", "M3"): 1, ("water", "LITRES"): 0.001}
df["unit_up"] = df.unit.str.upper().str.strip()
df["factor"] = [UNIT_FACTOR.get((u, x)) for u, x in zip(df.utility, df.unit_up)]
conv = df.factor != 1
for i in df.index[conv]:
    log_change(df.loc[i], "value", df.at[i, "value"], df.at[i, "value"] * df.at[i, "factor"],
               f"unit conversion {df.at[i, 'unit']} -> base unit", "rule")
df["value"] = df.value * df.factor
df["unit"] = df.utility.map({"electricity": "kWh", "gas": "kWh", "water": "m3"})
df = df.drop(columns=["unit_up", "factor"])

# --------------------------------------- 2. bills -> calendar months (pro-rata)
parts = []
for b in bills.itertuples():
    days = pd.date_range(b.billing_start, b.billing_end, freq="D")
    per_day = b.consumption / len(days)
    s = pd.Series(1, index=days).groupby(days.to_period("M")).size()
    for per, nd in s.items():
        parts.append((b.property_id, str(per), b.utility, per_day * nd, nd))
bm = (pd.DataFrame(parts, columns=KEY + ["bill_value", "bill_days"])
        .groupby(KEY, as_index=False).sum())
bm["days_in_month"] = bm.period.map(lambda p: pd.Period(p).days_in_month)
bm["bill_complete"] = bm.bill_days >= bm.days_in_month
bm = bm[bm.bill_complete][KEY + ["bill_value"]]

# --------------------------------------- 3. duplicates
df = df.merge(bm, on=KEY, how="left")
dup_mask = df.duplicated(KEY, keep=False)
keep_rows = []
for key, g in df[dup_mask].groupby(KEY):
    row = g.iloc[0]
    if g.value.nunique() == 1:
        log_issue(row, "duplicate_exact", "low", f"{len(g)} identical rows", "kept one")
        keep_rows.append(g.index[0])
    else:
        ref = row.bill_value
        best = g.index[0] if pd.isna(ref) else (g.value - ref).abs().idxmin()
        log_issue(row, "duplicate_conflicting", "medium",
                  f"values {sorted(g.value.round(1).tolist())}",
                  "kept value closest to bill" if pd.notna(ref) else "kept first, re-checked at reconciliation")
        keep_rows.append(best)
df = pd.concat([df[~dup_mask], df.loc[keep_rows]]).sort_values(KEY).reset_index(drop=True)
df["data_status"] = "validated"

# --------------------------------------- 3b. reference values per calendar month
# Calendar-aligned bills: the pro-rated bill IS the month's reference value.
# Offset billing cycles (e.g. 15th-14th): each bill spans two months, so simple
# pro-rating blurs month-to-month changes and would raise false mismatches.
# Instead, each month's value is "implied" from every bill that touches it,
# using the neighbouring month's submission:
#     implied(m) = (bill - submitted(other) * share_other) / share_m
# A month is flagged only when ALL its implied values disagree with what was
# submitted (so one bad neighbour cannot create a false alarm).
offset = props.set_index("property_id").billing_cycle_offset_days
aligned_ids = offset[offset == 0].index
ref = bm[bm.property_id.isin(aligned_ids)].rename(columns={"bill_value": "ref_value"})

periods = [str(p) for p in pd.period_range("2024-01", "2025-12", freq="M")]
bill_idx = bills.assign(start_p=bills.billing_start.dt.to_period("M").astype(str)) \
                .set_index(["property_id", "utility", "start_p"]).consumption
implied_rows = []
for pid_, off in offset[offset > 0].items():
    for util in df[df.property_id == pid_].utility.unique():
        S = df[(df.property_id == pid_) & (df.utility == util)].set_index("period").value
        S = S.where(S > 0)

        def implied_values(m, exclude=frozenset()):
            out = []
            pm = pd.Period(m)
            # bill starting in month m: (dim-off)/dim of m, off/dim of m+1
            for start, other, w_m, w_o in [
                (m, str(pm + 1), (pm.days_in_month - off) / pm.days_in_month,
                 off / (pm + 1).days_in_month),
                (str(pm - 1), str(pm - 1), off / pm.days_in_month,
                 ((pm - 1).days_in_month - off) / (pm - 1).days_in_month),
            ]:
                b = bill_idx.get((pid_, util, start))
                o = S.get(other)
                if b is not None and pd.notna(o) and other not in exclude:
                    out.append((b - o * w_o) / w_m)
            return out

        flagged = set()
        for m in periods:
            imp, v = implied_values(m), S.get(m)
            if imp and pd.notna(v) and all(abs(v / x - 1) > TOLERANCE for x in imp):
                flagged.add(m)
        for m in periods:
            imp = implied_values(m, exclude=frozenset(flagged))
            if imp:
                implied_rows.append((pid_, m, util, float(np.mean(imp))))
ref = pd.concat([ref, pd.DataFrame(implied_rows, columns=KEY + ["ref_value"])])
df = df.drop(columns="bill_value").merge(ref, on=KEY, how="left").rename(columns={"ref_value": "bill_value"})

# --------------------------------------- 4. validity + reconciliation vs bill
for i, r in df.iterrows():
    v, b = r.value, r.bill_value
    if v <= 0:
        log_issue(r, "zero_or_negative", "high", f"value={v}",
                  "replaced with bill" if pd.notna(b) else "set to null, to estimate")
        new = b if pd.notna(b) else np.nan
        log_change(r, "value", v, new, "invalid value", "bill" if pd.notna(b) else "pending")
        df.at[i, "value"] = new
        df.at[i, "data_status"] = "corrected_from_bill" if pd.notna(b) else "invalid"
        continue
    if pd.isna(b):
        continue
    ratio = v / b
    if abs(ratio - 1) <= TOLERANCE:
        continue
    if 0.0008 < ratio < 0.0012:
        rule, sev = "unit_mislabel", "high"
    elif 9 < ratio < 11 or 0.09 < ratio < 0.11:
        rule, sev = "decimal_shift", "high"
    else:
        rule, sev = "bill_mismatch", "medium"
    log_issue(r, rule, sev, f"submitted {v:,.1f} vs bill {b:,.1f} ({ratio - 1:+.1%})", "replaced with bill")
    log_change(r, "value", v, round(b, 1), rule, "bill")
    df.at[i, "value"] = round(b, 1)
    df.at[i, "data_status"] = "corrected_from_bill"

# --------------------------------------- 5. completeness: expected vs received
expected = []
for p in props.itertuples():
    for per in occ[occ.property_id == p.property_id].period:
        for u in ["electricity", "water"] + (["gas"] if p.has_gas else []):
            expected.append((p.property_id, per, u))
expected = pd.DataFrame(expected, columns=KEY)
df = (expected.merge(df, on=KEY, how="left").drop(columns="bill_value")
      .merge(ref.rename(columns={"ref_value": "bill_value"}), on=KEY, how="left"))
df["unit"] = df.utility.map({"electricity": "kWh", "gas": "kWh", "water": "m3"})
for i in df.index[df.data_status.isna()]:
    r = df.loc[i]
    if pd.notna(r.bill_value):
        log_issue(r, "missing_submission", "medium", "no portal submission", "filled from bill")
        log_change(r, "value", None, round(r.bill_value, 1), "missing submission", "bill")
        df.at[i, "value"], df.at[i, "data_status"] = round(r.bill_value, 1), "sourced_from_bill"
    else:
        log_issue(r, "missing_submission", "high", "no submission and no complete bill",
                  "estimated, chase property")
        df.at[i, "data_status"] = "invalid"

# --------------------------------------- 6. plausibility (intensity per room night)
df = df.merge(occ, on=["property_id", "period"])
df["intensity"] = df.value / df.occupied_room_nights


def robust_z(s):
    med = s.median()
    mad = (s - med).abs().median() or 1e-9
    return 0.6745 * (s - med) / mad


df["z"] = df.groupby(["property_id", "utility"]).intensity.transform(robust_z)
for i in df.index[df.z.abs() > MAD_Z_LIMIT]:
    r = df.loc[i]
    confirmed = pd.notna(r.bill_value) and abs(r.value / r.bill_value - 1) <= TOLERANCE
    reject = not confirmed and abs(r.z) > MAD_Z_REJECT
    log_issue(r, "intensity_outlier", "high" if reject else "medium",
              f"{r.intensity:.2f} {r.unit}/room-night (robust z={r.z:+.1f})",
              "confirmed by bill, flag to operations" if confirmed
              else "implausible: quarantined and estimated" if reject else "held for review")
    if confirmed:
        df.at[i, "data_status"] = "verified_anomaly"
    elif reject:
        df.at[i, "data_status"] = "invalid"

# --------------------------------------- 7. estimate remaining gaps
# Estimate = median intensity of the same property & utility x occupied room nights
med_int = df[df.data_status != "invalid"].groupby(["property_id", "utility"]).intensity.median()
for i in df.index[df.data_status == "invalid"]:
    r = df.loc[i]
    est = round(med_int[(r.property_id, r.utility)] * r.occupied_room_nights, 1)
    log_change(r, "value", r.value, est, "gap estimated: median intensity x room nights", "estimate")
    df.at[i, "value"], df.at[i, "data_status"] = est, "estimated"

clean = df[KEY + ["value", "unit", "data_status", "occupied_room_nights"]].copy()
clean = clean.merge(props[["property_id", "property_name", "country", "segment", "rooms"]], on="property_id")
clean.to_csv(OUT / "clean_consumption.csv", index=False)

# --------------------------------------- 8. invoice gap report (bills to chase)
exp_bills = []
for p in props.itertuples():
    for u in ["electricity", "water"] + (["gas"] if p.has_gas else []):
        for per in pd.period_range("2024-01", "2025-12", freq="M"):
            start = per.start_time + pd.Timedelta(days=p.billing_cycle_offset_days)
            end = (per + 1).start_time + pd.Timedelta(days=p.billing_cycle_offset_days - 1)
            if end <= pd.Timestamp("2025-12-31"):
                exp_bills.append((p.property_id, u, start.normalize()))
exp_bills = pd.DataFrame(exp_bills, columns=["property_id", "utility", "billing_start"])
gap = exp_bills.merge(bills[["property_id", "utility", "billing_start", "invoice_no"]],
                      on=["property_id", "utility", "billing_start"], how="left")
gap = gap[gap.invoice_no.isna()].drop(columns="invoice_no")
gap["action"] = "request invoice copy from provider"
gap.to_csv(OUT / "invoice_gap_report.csv", index=False)

# --------------------------------------- 9. emissions
clean = clean.merge(props[["property_id"]], on="property_id")
clean["ef"] = np.where(clean.utility == "electricity", clean.country.map(GRID_EF),
                       np.where(clean.utility == "gas", GAS_EF, 0.0))
clean["tco2e"] = clean.value * clean.ef / 1000
clean["scope"] = clean.utility.map({"electricity": "Scope 2", "gas": "Scope 1", "water": "-"})
em = (clean[clean.utility != "water"]
      .groupby(["property_id", "property_name", "country", "segment", "period", "scope"], as_index=False)
      .tco2e.sum())
em.to_csv(OUT / "emissions_monthly.csv", index=False)

# --------------------------------------- 10. logs + scorecard
issue_log = pd.DataFrame(issues)
issue_log.insert(0, "issue_id", [f"DQ-{i:05d}" for i in range(1, len(issue_log) + 1)])
issue_log.to_csv(OUT / "issue_log.csv", index=False)
pd.DataFrame(changes).to_csv(OUT / "change_log.csv", index=False)

score = (clean.groupby("property_id")
         .apply(lambda g: pd.Series({
             "records": len(g),
             "first_time_right_pct": round((g.data_status.isin(["validated", "verified_anomaly"])).mean() * 100, 1),
             "estimated_records": int((g.data_status == "estimated").sum()),
             "corrected_records": int((g.data_status == "corrected_from_bill").sum()),
         }), include_groups=False).reset_index())
score.to_csv(OUT / "property_scorecard.csv", index=False)

print(f"raw rows: {n_raw:,} -> clean rows: {len(clean):,}")
print(issue_log.rule.value_counts().to_string())
print(clean.data_status.value_counts().to_string())
print(f"missing invoices to chase: {len(gap)}")
