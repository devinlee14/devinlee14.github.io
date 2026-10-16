"""
Generate a SIMULATED spare-parts procurement dataset for a heavy-equipment
contractor (2 years, 14 suppliers, 420 part numbers, ~6,500 PO lines).

Procurement data is commercially sensitive, so this script builds a realistic
stand-in with the same tables an ERP (e.g. SAP MM) would export:

  suppliers.csv          supplier master: type (OEM / authorised distributor / aftermarket)
  parts.csv              part master: category, criticality, contract supplier, contract price
  purchase_orders.csv    one row per PO line: PR, PO and goods-receipt dates, quantities,
                         unit price, urgent flag, expedite cost
  invoices.csv           supplier invoices (for 3-way match: PO vs goods receipt vs invoice)
  daily_usage.csv        daily part consumption for the critical parts (for safety stock)

Behaviours built in (the analysis has to find them):
  * 1 in 5 lines is bought off-contract ("maverick"), mostly when urgent, at a premium
  * urgent orders pay +10-18% price and an expedite (air freight) charge
  * POs above USD 5,000 need a second approval and wait longer before release
  * aftermarket suppliers are cheaper but late and reject more; OEM imports have long lead times
  * a few invoices do not match the PO price or the received quantity
Run:  python src/generate_data.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

rng = np.random.default_rng(2024)
OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)

# ------------------------------------------------------------------ suppliers
# name, type, price index vs OEM list, lead-time mean / sd (days), on-time prob, reject rate
SUP = [
    ("SUP-01", "OEM Parts Centre Jakarta", "OEM", 1.00, 26, 6, 0.90, 0.004),
    ("SUP-02", "OEM Regional Hub Singapore", "OEM", 0.98, 33, 9, 0.84, 0.005),
    ("SUP-03", "Nusantara Heavy Parts", "Authorised distributor", 0.95, 9, 3, 0.93, 0.010),
    ("SUP-04", "Borneo Equipment Supply", "Authorised distributor", 0.94, 11, 4, 0.88, 0.012),
    ("SUP-05", "Sumatra Traktor Parts", "Authorised distributor", 0.96, 8, 2, 0.95, 0.008),
    ("SUP-06", "Celebes Machinery Spares", "Authorised distributor", 0.93, 14, 6, 0.80, 0.015),
    ("SUP-07", "Prima Hydraulic", "Aftermarket", 0.78, 6, 3, 0.78, 0.045),
    ("SUP-08", "Mitra Filter Indonesia", "Aftermarket", 0.72, 4, 2, 0.90, 0.020),
    ("SUP-09", "Jaya Undercarriage", "Aftermarket", 0.80, 7, 4, 0.74, 0.060),
    ("SUP-10", "Sentosa Engine Parts", "Aftermarket", 0.76, 8, 5, 0.70, 0.055),
    ("SUP-11", "Bintang Electrical", "Aftermarket", 0.82, 5, 2, 0.86, 0.030),
    ("SUP-12", "Garuda GET & Wear Parts", "Aftermarket", 0.79, 6, 3, 0.83, 0.035),
    ("SUP-13", "Delta Tyre & Rim", "Authorised distributor", 0.97, 10, 4, 0.89, 0.010),
    ("SUP-14", "Kalimantan Spares Trading", "Aftermarket", 0.84, 9, 6, 0.68, 0.050),
]
sup = pd.DataFrame(SUP, columns=["supplier_id", "supplier_name", "supplier_type", "price_index",
                                 "lt_mean", "lt_sd", "p_on_time", "reject_rate"])
sup[["supplier_id", "supplier_name", "supplier_type"]].to_csv(OUT / "suppliers.csv", index=False)
S = sup.set_index("supplier_id")

# category: (share of parts, base price lognormal median USD, sigma, eligible suppliers)
CATS = {
    "Hydraulic": (0.20, 650, 1.0, ["SUP-01", "SUP-02", "SUP-03", "SUP-04", "SUP-07"]),
    "Engine": (0.18, 900, 1.1, ["SUP-01", "SUP-02", "SUP-05", "SUP-06", "SUP-10"]),
    "Undercarriage": (0.12, 1800, 0.9, ["SUP-01", "SUP-03", "SUP-04", "SUP-09"]),
    "Filters & Lubricants": (0.16, 45, 0.7, ["SUP-01", "SUP-03", "SUP-05", "SUP-08"]),
    "Electrical": (0.14, 220, 0.9, ["SUP-01", "SUP-05", "SUP-06", "SUP-11"]),
    "Ground Engaging Tools": (0.10, 380, 0.8, ["SUP-03", "SUP-04", "SUP-12", "SUP-14"]),
    "Tyres & Rims": (0.10, 2600, 0.6, ["SUP-13", "SUP-04", "SUP-14"]),
}

# ------------------------------------------------------------------ parts
parts = []
n_parts = 420
cat_names = list(CATS)
cat_counts = (np.array([CATS[c][0] for c in cat_names]) * n_parts).round().astype(int)
pid = 0
for c, k in zip(cat_names, cat_counts):
    _, med, sig, elig = CATS[c]
    for _ in range(k):
        pid += 1
        price = float(rng.lognormal(np.log(med), sig))
        # cheap consumables are used a lot; expensive components rarely
        demand = max(1, int(rng.lognormal(np.log(2500 / max(price, 20) ** 0.6), 1.35)))
        contract = rng.choice(elig, p=None)
        parts.append(dict(part_no=f"P-{pid:04d}", category=c,
                          description=f"{c} part {pid:04d}",
                          oem_list_price_usd=round(price, 2),
                          annual_demand=demand,
                          critical=bool(rng.random() < (0.35 if c in ["Hydraulic", "Engine", "Undercarriage"] else 0.12)),
                          contract_supplier=contract,
                          contract_price_2024=round(price * S.loc[contract, "price_index"], 2),
                          eligible=";".join(elig)))
parts = pd.DataFrame(parts)
parts.drop(columns="eligible").to_csv(OUT / "parts.csv", index=False)

# ------------------------------------------------------------------ PO lines
sites = ["Site A - Kalimantan", "Site B - Sumatra", "Site C - Sulawesi", "Site D - Papua"]
site_urgent = {"Site A - Kalimantan": 0.15, "Site B - Sumatra": 0.12,
               "Site C - Sulawesi": 0.28, "Site D - Papua": 0.24}   # planning maturity differs
days = pd.date_range("2024-01-01", "2025-12-31", freq="D")
po_rows, inv_rows = [], []
line = 0
for p in parts.itertuples():
    elig = p.eligible.split(";")
    # number of order lines over 2 years ~ demand / typical order size
    n_lines = int(np.clip(rng.poisson(max(2, p.annual_demand * 2 / max(3, p.annual_demand / 10))), 2, 60))
    for _ in range(n_lines):
        line += 1
        site = rng.choice(sites, p=[0.3, 0.25, 0.25, 0.2])
        urgent = rng.random() < site_urgent[site] * (1.4 if p.critical else 0.8)
        pr_date = days[rng.integers(0, len(days) - 60)]
        # supplier choice: contract supplier unless maverick
        maverick = rng.random() < (0.45 if urgent else 0.09)
        if maverick:
            others = [s for s in elig if s != p.contract_supplier] or elig
            # urgent buyers pick whoever is fastest locally
            weights = np.array([1 / S.loc[s, "lt_mean"] for s in others])
            supplier = rng.choice(others, p=weights / weights.sum())
        else:
            supplier = p.contract_supplier
        year_infl = 1.0 if pr_date.year == 2024 else 1.045
        if supplier == p.contract_supplier:
            unit_price = p.contract_price_2024 * year_infl
        else:  # spot price: list price x supplier index x spot premium
            unit_price = p.oem_list_price_usd * S.loc[supplier, "price_index"] * year_infl * rng.uniform(1.04, 1.12)
        if urgent:
            unit_price *= rng.uniform(1.10, 1.18)
        unit_price = round(unit_price * rng.normal(1, 0.01), 2)
        qty = int(max(1, rng.poisson(max(1, p.annual_demand / 12)) if not urgent else rng.integers(1, 4)))
        value = unit_price * qty
        # PR -> PO approval: second approval above USD 5,000
        appr = rng.gamma(2.0, 1.2) + (rng.gamma(3.0, 1.8) if value > 5000 else 0)
        if urgent:
            appr *= 0.35
        po_date = pr_date + pd.Timedelta(days=round(appr, 1))
        lt_quoted = max(2, round(S.loc[supplier, "lt_mean"] * (0.55 if urgent else 1)))
        promised = po_date + pd.Timedelta(days=lt_quoted)
        late = rng.random() > S.loc[supplier, "p_on_time"]
        delay = rng.gamma(2, S.loc[supplier, "lt_sd"] / 2) if late else -rng.uniform(0, 1.5)
        received = promised + pd.Timedelta(days=round(delay, 1))
        partial = rng.random() < (0.10 if S.loc[supplier, "supplier_type"] == "Aftermarket" else 0.04)
        qty_rec = qty if not partial else max(0, qty - int(np.ceil(qty * rng.uniform(0.2, 0.6))))
        rejected = int(rng.binomial(qty_rec, S.loc[supplier, "reject_rate"]))
        expedite = round(value * rng.uniform(0.06, 0.12) + rng.uniform(80, 400), 2) if urgent else 0.0
        po_no = f"PO-{24 if pr_date.year == 2024 else 25}{line:05d}"
        po_rows.append(dict(po_line=po_no, part_no=p.part_no, supplier_id=supplier, site=site,
                            pr_date=pr_date.date(), po_date=po_date.date(), promised_date=promised.date(),
                            gr_date=received.date(), qty_ordered=qty, qty_received=qty_rec,
                            qty_rejected=rejected, unit_price_usd=unit_price, urgent=bool(urgent),
                            expedite_cost_usd=expedite))
        # invoice: mostly matches; some price or quantity exceptions
        inv_price, inv_qty = unit_price, qty_rec
        r = rng.random()
        if r < 0.025:
            inv_price = round(unit_price * rng.uniform(1.03, 1.15), 2)       # price above PO
        elif r < 0.040:
            inv_qty = qty                                                     # billed for undelivered qty
        elif r < 0.046:
            inv_qty = qty_rec * 2                                             # duplicate billing
        inv_rows.append(dict(invoice_no=f"INV-{line:06d}", po_line=po_no, supplier_id=supplier,
                             invoice_date=(received + pd.Timedelta(days=int(rng.integers(1, 20)))).date(),
                             qty_invoiced=inv_qty, unit_price_invoiced=inv_price))

po = pd.DataFrame(po_rows)
po.to_csv(OUT / "purchase_orders.csv", index=False)
pd.DataFrame(inv_rows).to_csv(OUT / "invoices.csv", index=False)

# ------------------------------------------------------------------ daily usage (critical parts)
use = []
for p in parts[parts.critical].itertuples():
    lam = p.annual_demand / 365
    for d in pd.date_range("2025-01-01", "2025-12-31", freq="D"):
        q = rng.poisson(lam * (1.3 if d.month in [3, 4, 9, 10] else 1.0))
        if q:
            use.append((p.part_no, d.date(), int(q)))
pd.DataFrame(use, columns=["part_no", "date", "qty_used"]).to_csv(OUT / "daily_usage.csv", index=False)

print(f"suppliers {len(sup)} | parts {len(parts)} | PO lines {len(po):,} | spend USD {(po.unit_price_usd*po.qty_ordered).sum():,.0f}")
print(po.urgent.mean(), (po.supplier_id != po.part_no.map(parts.set_index('part_no').contract_supplier)).mean())
