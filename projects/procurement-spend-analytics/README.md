# Heavy Equipment Spare Parts Procurement Analytics

**Spend, supplier performance, savings and inventory analysis of USD 51M of spare-parts purchasing for a heavy-equipment contractor (4 sites, 14 suppliers, 420 part numbers, 6,591 PO lines over 2024–2025).**

> **Data note:** procurement data is commercially sensitive, so this project uses a **simulated dataset** (`src/generate_data.py`). It has the same structure as an ERP export (e.g. SAP MM): supplier and part masters, purchase-order lines with requisition, PO and goods-receipt dates, supplier invoices, and daily part usage. The analysis is written as if the patterns were unknown.

## Business problem
Spare parts keep machines running, but buying them well is hard. The fleet runs on hydraulics, engines, undercarriage, tyres and wear parts from OEMs, authorised distributors and aftermarket suppliers. Procurement managers need answers to five questions:
1. Where does the money go, and which parts matter most?
2. Which suppliers deliver on time, in full and to quality?
3. How much are we paying for urgent and off-contract buying?
4. Where does the purchasing process slow down?
5. How much stock should we hold of critical parts so a breakdown doesn't wait for a part?

## Data
| File | Rows | Description |
|---|---|---|
| `suppliers.csv` | 14 | OEM, authorised distributor or aftermarket |
| `parts.csv` | 420 | category, criticality, contract supplier, contract price |
| `purchase_orders.csv` | 6,591 | PR / PO / promised / goods-receipt dates, quantities, rejects, price, urgent flag, expedite cost |
| `invoices.csv` | 6,591 | invoiced quantity and price (for 3-way match) |
| `daily_usage.csv` | ~7.5k | 2025 daily consumption of critical parts |

## Analysis
| Step | File | Techniques |
|---|---|---|
| Spend by category and supplier type | `sql/01_spend_overview.sql` | aggregation, share of total |
| ABC (Pareto) classification of parts | `sql/02_abc_classification.sql` | running `SUM() OVER`, `ROW_NUMBER` |
| Supplier scorecard: OTIF, lead time & variability, reject rate, price vs contract, composite score | `sql/03_supplier_scorecard.sql` | conditional aggregation, `STDDEV_SAMP` |
| Urgent and off-contract buying cost by site | `sql/04_maverick_and_urgent.sql` | price premium vs contract + expedite cost |
| Procure-to-receive cycle by PO value band | `sql/05_cycle_time.sql` | `MEDIAN`, `QUANTILE_CONT` |
| 3-way match (PO vs goods receipt vs invoice) | `sql/06_three_way_match.sql` | rule-based exception classification |
| Savings sizing and safety stock / reorder points | `src/analysis.py` | scenario sizing; ROP = d·L + z·√(L·σd² + d²·σL²) at 95% service |

Run: `python src/generate_data.py && python src/run_analysis.py && python src/analysis.py`

## Key findings
- **Spend is concentrated:** 98 of 420 part numbers (**23%**) account for **80%** of spend. Engine parts (25%), tyres & rims (17%) and hydraulics (17%) lead.
- **Overall OTIF is 82.5%.** Authorised distributors perform best (top supplier: 93.8% OTIF, 0.75% rejects, 1.8-day lead-time variability).
- **Cheap is not cheap:** aftermarket suppliers are only 0–2.5% below contract price, but deliver on time and in full 60–85% of the time and reject up to **5.8%** of parts. The two weakest scored 45–46 out of 100.
- **Long-lead OEM imports drive risk:** the Singapore OEM hub averages 32 days with ±7.4 days variability, the main reason critical engine parts need buffer stock.
- **Urgent buying is a planning problem:** 17.5% of PO lines are urgent. Sulawesi (26%) and Papua (23%) are twice as high as Kalimantan and Sumatra (~12%). Urgent lines pay 10–18% more plus air-freight expediting.
- **Approval is the slowest step for big orders:** POs above USD 5,000 wait a median **7 days** for approval (p90: 12) vs 2 days below USD 5,000.
- **3.3% of invoices don't match** the PO or goods receipt (price above PO, duplicate billing). That's USD 370k of overbilling over two years if paid without checks.

## Savings and recommendations (about USD 522k per year, 2.0% of annual spend)
| Lever | USD / year |
|---|---|
| Stop planned off-contract buying (buy from the contract supplier at contract price) | ~194k |
| Block overbilled invoices with an automated 3-way match before payment | ~185k |
| Cut urgent orders at every site to the best site's rate (11.5%) through better parts planning | ~144k |

Further actions:
1. **Set reorder points with safety stock for 45 critical A/B parts** (95% service level), about USD 156k of one-off buffer stock. Reordering at average lead-time demand, with no buffer, runs out of stock in roughly half of replenishment cycles.
2. **Speed up approval for contract items:** auto-approve contract-priced POs within budget, or approve in parallel, to cut the 5-day wait on larger orders.
3. **Supplier strategy:** concentrate volume on the top-scoring distributors, and put suppliers below 70% OTIF or above 5% rejects on an improvement plan or phase them out.
4. **Plan parts with maintenance:** kit parts for scheduled PM at Sulawesi and Papua, where most urgent buying happens.

## Tools
SQL (DuckDB) · Python (pandas, NumPy, SciPy) · spend analysis · ABC/Pareto · supplier scorecard · 3-way match · inventory safety stock
