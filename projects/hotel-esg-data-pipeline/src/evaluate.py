"""
Score the pipeline against the answer key that generate_data.py kept aside.

Because the data is simulated, we know which errors were injected and what the
true consumption was. This lets us measure the pipeline honestly:
  * detection recall per error type
  * false alarms (records changed although nothing was wrong)
  * accuracy of the dataset before vs after the pipeline

Run:  python src/evaluate.py   (after pipeline.py)
"""
from pathlib import Path
import json
import re
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "outputs"
KEY = ["property_id", "period", "utility"]


def norm(df):
    df = df.copy()
    df["property_id"] = df.property_id.map(
        lambda x: f"HTL-{int(re.search(r'(\d+)', str(x)).group(1)):03d}")
    df["period"] = df.period.map(
        lambda x: pd.Period(pd.to_datetime(str(x).replace("/", "-"), format="mixed"), "M").strftime("%Y-%m"))
    return df


truth = pd.read_csv(DATA / "_ground_truth.csv")
key = norm(pd.read_csv(DATA / "_answer_key.csv"))
issues = pd.read_csv(OUT / "issue_log.csv")
clean = pd.read_csv(OUT / "clean_consumption.csv")
raw = norm(pd.read_csv(DATA / "portal_submissions.csv"))

# ---- detection recall: was each injected error caught by any rule?
flagged = set(map(tuple, issues[KEY].values))
inj = key[key.error_injected.ne("none")].drop_duplicates(KEY + ["error_injected"])
# missing rows are not in the answer-key file (they were dropped); rebuild them
expected = truth[KEY]
present = set(map(tuple, raw[KEY].values))
missing = expected[[tuple(r) not in present for r in expected.values]].assign(error_injected="missing")
inj = pd.concat([inj[inj.error_injected != "id_format"], missing])
inj["caught"] = [tuple(r) in flagged for r in inj[KEY].values]
recall = inj.groupby("error_injected").caught.agg(["sum", "count"])
recall["recall_pct"] = (recall["sum"] / recall["count"] * 100).round(1)

# ---- accuracy before vs after (record-level absolute % error vs truth)
t = truth.rename(columns={"value": "true"})
raw_std = raw.copy()
f = {("electricity", "KWH"): 1, ("electricity", "MWH"): 1000, ("gas", "KWH"): 1,
     ("water", "M3"): 1, ("water", "LITRES"): 0.001}
raw_std["value"] = raw_std.value * [f[(u, x.upper())] for u, x in zip(raw_std.utility, raw_std.unit)]
before = t.merge(raw_std.drop_duplicates(KEY), on=KEY, how="left")
after = t.merge(clean, on=KEY, how="left")


def err_stats(d):
    e = ((d.value - d.true).abs() / d.true)
    return dict(records_within_2pct=round(((e <= 0.02) & d.value.notna()).mean() * 100, 1),
                missing_records=int(d.value.isna().sum()),
                portfolio_total_error_pct=round(abs(d.value.where(d.value > 0).sum() - d.true.sum())
                                                / d.true.sum() * 100, 2))


# id_format rows are quarantined only if the ID cannot be repaired; they are
# repaired automatically, so they count as handled by standardisation.
summary = dict(
    recall_by_error=recall.reset_index().to_dict("records"),
    overall_recall_pct=round(inj.caught.mean() * 100, 1),
    before=err_stats(before),
    after=err_stats(after),
)
changed = pd.read_csv(OUT / "change_log.csv")
changed = changed[changed.field == "value"]
bad = set(map(tuple, inj[KEY].values)) | set(map(tuple, key[key.error_injected.str.startswith("dup")][KEY].values))
unit_conv = changed.reason.str.startswith("unit conversion")
fa = changed[~unit_conv & ~changed[KEY].apply(tuple, axis=1).isin(bad)]
summary["false_alarm_changes"] = int(len(fa))
(OUT / "evaluation.json").write_text(json.dumps(summary, indent=2))
print(recall.to_string())
print(json.dumps({k: v for k, v in summary.items() if k != "recall_by_error"}, indent=2))
