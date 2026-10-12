# Hotel Utility Data Pipeline & ESG Reporting

**Automated validation, bill reconciliation and gap-filling for 40 hotels' utility data, with a full audit trail, and Scope 1 & 2 emissions as the output.**

> **Data note:** real hotel utility data is confidential, so this project uses a **simulated dataset** built by `src/generate_data.py`. Realistic errors are injected on purpose, and the answer key is kept aside, so the pipeline can be scored honestly (see *Results*).

## Business problem
Sustainability reporting depends on hundreds of monthly utility figures that hotel engineers type into a portal by hand. Typical problems:
- figures that don't match the utility bill
- MWh entered as kWh, or decimals shifted
- months that are missing or submitted twice
- property IDs and period formats that are inconsistent

If these go unchecked, the reported carbon footprint is simply wrong. The goal: **turn raw submissions into audit-ready, reconciled data, and show every change that was made.**

## Data
| File | Rows | Description |
|---|---|---|
| `properties.csv` | 40 | property master: country, segment, rooms, floor area, billing cycle |
| `occupancy.csv` | 960 | occupied room nights per property-month |
| `portal_submissions.csv` | 2,364 | values typed in by properties (contains the errors) |
| `utility_bills.csv` | ~2,330 | invoice register (source of truth). Some bills run on **offset cycles** (e.g. 15th–14th), and ~1.5% never arrived |

## Pipeline (`src/pipeline.py`)
1. **Standardise:** repair property IDs (`htl-001`, `HTL001` → `HTL-001`), unify period formats (`2024/03`, `Mar-2024` → `2024-03`), convert units (MWh → kWh, litres → m³).
2. **De-duplicate:** drop exact duplicates; for conflicting duplicates, keep the value closest to the bill.
3. **Build reference values:** pro-rate calendar-aligned bills to months. For **offset billing cycles**, derive each month's *implied* value from both bills that touch it, and flag a month only when *every* implied value disagrees. This avoids false alarms that naive pro-rating creates.
4. **Validate & reconcile** (tolerance ±2%), then classify the cause: *unit mislabel* (ratio ≈ 0.001), *decimal shift* (≈ 10×), or *transcription mismatch*. Each case is corrected from the bill and logged.
5. **Completeness:** compare expected vs received property-month-utility records. Fill gaps from bills; when no bill exists, estimate from median intensity × occupied room nights (flagged `estimated`).
6. **Plausibility:** robust z-score (median/MAD) on consumption per occupied room night. Outliers confirmed by the bill are kept as `verified_anomaly` and escalated to operations (e.g. a water leak); implausible values without a bill are quarantined.
7. **Invoice gap report:** list expected vs received bills, so the team knows which invoices to chase.
8. **Emissions:** Scope 2 (electricity × grid factor) and Scope 1 (natural gas), plus carbon intensity per occupied room night.

Every action is written to `issue_log.csv` (what was found, by which rule, what was done) and `change_log.csv` (old → new value, reason, source). Every number is traceable.

## Results (`src/evaluate.py`, scored against the hidden answer key)
| Metric | Before | After |
|---|---|---|
| Records within ±2% of true value | 93.0% | **100%** |
| Missing records | 72 | **0** |
| Injected errors detected | — | **99.5%** (199 of 200) |
| Correct values wrongly changed (false alarms) | — | **0** |

- 388 formatting/unit fixes applied automatically; 201 issues logged with rule, severity and action
- 35 missing invoices identified for follow-up with providers
- A real water leak (HTL-017, Jun–Jul 2025, 2.6× normal) was **kept, not "fixed"**, because the bill confirmed it, and was escalated as an operational issue

The one missed error was a 2.0% transcription difference sitting right at the tolerance limit. This is an expected trade-off of a ±2% threshold.

## Run it
```bash
pip install pandas numpy
python src/generate_data.py   # simulated inputs
python src/pipeline.py        # clean data + logs
python src/evaluate.py        # score vs answer key
```

## Tools
Python (pandas, NumPy) · rule-based validation · robust statistics (MAD) · data reconciliation · audit logging

*Emission factors are illustrative approximations of national grid averages. A real engagement would use the client-approved factor set.*
