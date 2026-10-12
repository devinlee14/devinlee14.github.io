"""
Generate a SIMULATED multi-property hotel utility dataset.

Real hotel utility data is confidential, so this script builds a realistic
stand-in: 40 fictional hotels in 8 countries, 24 months of electricity,
water and gas data, plus an independent utility-bill register.

Two files mimic what a data operations team actually receives:
  * portal_submissions.csv : monthly values typed in by each property
  * utility_bills.csv      : the invoice register (source of truth)

Typical real-world errors are injected on purpose into the submissions
(missing months, duplicates, unit mix-ups, decimal shifts, typos in IDs,
inconsistent period formats, transcription mismatches) so the validation
pipeline in pipeline.py has something real to catch.

Run:  python src/generate_data.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)
OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)

MONTHS = pd.period_range("2024-01", "2025-12", freq="M")

# country, cities, climate profile (1 = hot all year, 0 = strong seasons)
COUNTRIES = {
    "Singapore": (["Singapore"], 1.0),
    "Indonesia": (["Jakarta", "Bali", "Surabaya"], 1.0),
    "Thailand": (["Bangkok", "Phuket"], 0.9),
    "Malaysia": (["Kuala Lumpur", "Penang"], 1.0),
    "Vietnam": (["Ho Chi Minh City", "Da Nang"], 0.85),
    "Japan": (["Tokyo", "Osaka"], 0.3),
    "Australia": (["Sydney", "Melbourne"], 0.35),
    "United Arab Emirates": (["Dubai"], 0.6),
}
BRANDS = ["Azure", "Meridian Bay", "Palm Court", "Riverstone", "Cedar House"]
SEGMENTS = {"Luxury": (1.45, 1.6), "Upscale": (1.15, 1.25), "Midscale": (0.85, 0.9)}

# ---------------------------------------------------------------- properties
rows = []
pid = 1
country_list = list(COUNTRIES)
for i in range(40):
    country = country_list[i % len(country_list)]
    cities, climate = COUNTRIES[country]
    city = cities[(i // len(country_list)) % len(cities)]
    segment = rng.choice(list(SEGMENTS), p=[0.3, 0.45, 0.25])
    rooms = int(rng.integers(120, 480))
    rows.append(
        dict(
            property_id=f"HTL-{pid:03d}",
            property_name=f"{BRANDS[i % len(BRANDS)]} {city}",
            city=city,
            country=country,
            segment=segment,
            rooms=rooms,
            floor_area_m2=int(rooms * rng.uniform(55, 85) * SEGMENTS[segment][1]),
            has_gas=bool(rng.random() < 0.6),
            billing_cycle_offset_days=int(rng.choice([0, 0, 0, 14, 20])),
        )
    )
    pid += 1
props = pd.DataFrame(rows)
props.to_csv(OUT / "properties.csv", index=False)

# ------------------------------------------------- true monthly consumption
true_rows = []
for _, p in props.iterrows():
    climate = COUNTRIES[p.country][1]
    base_occ = rng.uniform(0.62, 0.85)
    seg_mult = SEGMENTS[p.segment][0]
    for m in MONTHS:
        days = m.days_in_month
        season = 1 + (1 - climate) * 0.18 * np.cos((m.month - 7.5) / 12 * 2 * np.pi)
        occ = np.clip(base_occ + rng.normal(0, 0.05) + 0.04 * np.sin(m.month / 12 * 2 * np.pi), 0.35, 0.97)
        orn = int(p.rooms * days * occ)  # occupied room nights
        elec = (p.floor_area_m2 * 0.62 * days * season + orn * 19 * seg_mult) * rng.normal(1, 0.03)
        water = (orn * 0.72 * seg_mult + p.floor_area_m2 * 0.004 * days) * rng.normal(1, 0.04)
        gas = (orn * 9.5 * seg_mult * (2 - season)) * rng.normal(1, 0.05) if p.has_gas else None
        true_rows.append(dict(property_id=p.property_id, period=str(m), occupied_room_nights=orn,
                              electricity_kwh=elec, water_m3=water, gas_kwh=gas))
truth = pd.DataFrame(true_rows)

# a genuine anomaly: a water leak at one property (real, not a data error)
leak = (truth.property_id == "HTL-017") & truth.period.isin(["2025-06", "2025-07"])
truth.loc[leak, "water_m3"] *= 2.6

occ = truth[["property_id", "period", "occupied_room_nights"]]
occ.to_csv(OUT / "occupancy.csv", index=False)

long = truth.melt(id_vars=["property_id", "period"],
                  value_vars=["electricity_kwh", "water_m3", "gas_kwh"],
                  var_name="utility", value_name="value").dropna()
long["utility"] = long.utility.str.split("_").str[0]
long["unit"] = long.utility.map({"electricity": "kWh", "water": "m3", "gas": "kWh"})
long["value"] = long.value.round(1)
# ground truth, used ONLY by evaluate.py to score the pipeline afterwards
long.to_csv(OUT / "_ground_truth.csv", index=False)

# ------------------------------------------------------ utility bill register
# Bills follow each property's billing cycle (some start mid-month), so they
# have to be pro-rated to calendar months before reconciliation.
TARIFF = {"electricity": 0.19, "water": 1.9, "gas": 0.07}
bill_rows = []
inv = 100000
for _, p in props.iterrows():
    sub = long[long.property_id == p.property_id]
    for util, g in sub.groupby("utility"):
        g = g.set_index("period")["value"]
        off = p.billing_cycle_offset_days
        for m in MONTHS:
            start = m.start_time + pd.Timedelta(days=off)
            end = (m + 1).start_time + pd.Timedelta(days=off) - pd.Timedelta(days=1)
            if end > MONTHS[-1].end_time:
                continue
            # consumption in [start, end] = share of month m + share of month m+1
            d1 = (m.end_time.normalize() - start).days + 1
            cons = g[str(m)] * d1 / m.days_in_month
            if off:
                nxt = str(m + 1)
                if nxt in g.index:
                    cons += g[nxt] * off / (m + 1).days_in_month
            inv += 1
            bill_rows.append(dict(invoice_no=f"INV-{inv}", property_id=p.property_id, utility=util,
                                  billing_start=start.date(), billing_end=end.date(),
                                  consumption=round(cons, 1),
                                  unit="kWh" if util != "water" else "m3",
                                  amount_usd=round(cons * TARIFF[util] * rng.normal(1, 0.01), 2)))
bills = pd.DataFrame(bill_rows)
# ~1.5% of invoices never arrive from the provider (gap the tracker must catch)
bills = bills.drop(index=rng.choice(bills.index, size=int(len(bills) * 0.015), replace=False))
bills.to_csv(OUT / "utility_bills.csv", index=False)

# -------------------------------------------- portal submissions + errors
sub = long.copy().reset_index(drop=True)
sub["submitted_by"] = sub.property_id.str.replace("HTL-", "eng.") + "@hotel.example"
n = len(sub)
sub["error_injected"] = "none"


def pick(frac, eligible=None):
    pool = sub.index if eligible is None else sub.index[eligible]
    pool = [i for i in pool if sub.at[i, "error_injected"] == "none"]
    return rng.choice(pool, size=int(n * frac), replace=False)


# 1. legitimate unit variety (not errors - must be standardised)
idx = pick(0.06, sub.utility.eq("electricity"))
sub.loc[idx, "value"] = (sub.loc[idx, "value"] / 1000).round(3)
sub.loc[idx, "unit"] = "MWh"
idx = pick(0.04, sub.utility.eq("water"))
sub.loc[idx, "value"] = (sub.loc[idx, "value"] * 1000).round(0)
sub.loc[idx, "unit"] = "Litres"
sub.loc[pick(0.05), "unit"] = sub.unit.str.upper()  # 'KWH', 'M3'

# 2. unit mislabel: value is MWh but unit says kWh
idx = pick(0.008, sub.utility.eq("electricity"))
sub.loc[idx, "value"] = (sub.loc[idx, "value"] / 1000).round(3)
sub.loc[idx, "error_injected"] = "unit_mislabel"

# 3. decimal shift (x10)
idx = pick(0.007)
sub.loc[idx, "value"] = sub.loc[idx, "value"] * 10
sub.loc[idx, "error_injected"] = "decimal_shift"

# 4. negative / zero values
idx = pick(0.004)
sub.loc[idx, "value"] = rng.choice([0, -1], size=len(idx)) * sub.loc[idx, "value"]
sub.loc[idx, "error_injected"] = "zero_or_negative"

# 5. transcription mismatch vs bill (2-15% off)
idx = pick(0.02)
sub.loc[idx, "value"] = (sub.loc[idx, "value"] * rng.choice([-1, 1], len(idx))
                         * rng.uniform(0.02, 0.15, len(idx)) + sub.loc[idx, "value"]).round(1)
sub.loc[idx, "error_injected"] = "bill_mismatch"

# 6. property ID typos
idx = pick(0.005)
sub.loc[idx, "property_id"] = [rng.choice([p.lower(), p.replace("-", ""), " " + p + " "])
                               for p in sub.loc[idx, "property_id"]]
sub.loc[idx, "error_injected"] = "id_format"

# 7. inconsistent period formats
idx = pick(0.06)
sub.loc[idx, "period"] = [rng.choice([p.replace("-", "/"), pd.Period(p).strftime("%b-%Y")])
                          for p in sub.loc[idx, "period"]]

# 8. missing submissions
missing = pick(0.03)
sub.loc[missing, "error_injected"] = "missing"
truth_missing = sub.loc[missing, ["property_id", "period", "utility"]].copy()

# 9. duplicates (some exact, some conflicting)
dup_idx = pick(0.015)
dups = sub.loc[dup_idx].copy()
conf = rng.random(len(dups)) < 0.4
dups.loc[conf, "value"] = (dups.loc[conf, "value"] * rng.uniform(0.85, 1.15, conf.sum())).round(1)
dups["error_injected"] = np.where(conf, "duplicate_conflicting", "duplicate_exact")

sub = pd.concat([sub.drop(index=missing), dups]).sample(frac=1, random_state=SEED)
sub["submitted_at"] = [
    (pd.Period(pd.to_datetime(p.replace("/", "-"), format="mixed"), "M").end_time
     + pd.Timedelta(days=int(rng.integers(3, 25)))).date()
    for p in sub.period
]
sub = sub[["property_id", "period", "utility", "value", "unit", "submitted_by", "submitted_at", "error_injected"]]

# the answer key is kept separately; the pipeline never reads it
sub[["property_id", "period", "utility", "error_injected"]].to_csv(OUT / "_answer_key.csv", index=False)
sub.drop(columns="error_injected").to_csv(OUT / "portal_submissions.csv", index=False)

print(f"properties: {len(props)} | submissions: {len(sub):,} | bills: {len(bills):,}")
print(sub.error_injected.value_counts().to_string())
