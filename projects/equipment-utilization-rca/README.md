# Heavy Equipment Availability & Downtime Root Cause Analysis (SQL)

**SQL analysis of 17,520 unit-days and 1,620 maintenance events from a 48-unit heavy-equipment fleet across 4 sites. Measures availability and utilisation, then finds the root causes of lost hours.**

> **Data note:** operational fleet data is confidential, so this project uses a **simulated dataset** (`src/generate_data.py`) modelled on how mining and construction contractors record fleet data: hour-meters, shift hours, breakdown and PM work orders. The analysis is written as if the causes were unknown.

## Business problem
Site managers see machines "not working" but can't tell why. The possible causes: breakdowns, waiting for parts, skipped maintenance, or rain. Each needs a different fix. **Goal: separate the causes and size the hours each one costs.**

## KPIs used
- **Physical Availability (PA)** = (scheduled − downtime) / scheduled → is the machine ready to work?
- **Use of Availability (UA)** = operating / available hours → when ready, is it used?
- **MTBF** = operating hours per breakdown · **MTTR** = mean hours to restore

## SQL analysis (`sql/`)
| File | Question | Techniques |
|---|---|---|
| `01_fleet_kpis.sql` | PA, UA, weather standby by site and month | aggregation, `GROUP BY ALL` |
| `02_mtbf_mttr.sql` | reliability by site and model | CTE joins, rate metrics |
| `03_downtime_pareto.sql` | which systems cause most downtime | running share `SUM() OVER` |
| `04_mttr_decomposition.sql` | repair vs waiting parts vs waiting mechanic | `QUANTILE_CONT … FILTER` |
| `05_pm_compliance_vs_failures.sql` | does overdue PM raise breakdown rate? | `LAG` over hour-meter, correlated subquery, exposure-based rates |
| `06_repeat_failures.sql` | same unit and system failing again within 30 days | `LAG() OVER (PARTITION BY unit, system)` |
| `07_bad_actors.sql` | top 10 units by downtime | `DENSE_RANK`, `QUALIFY` |

Run: `python src/generate_data.py && python src/run_analysis.py`

## Key findings
- **Fleet PA is healthy at 94.2%, but UA is only 72.5%.** Most "idle" machines are ready to work and simply not being used.
- **Low utilisation is seasonal, not mechanical:** UA falls from **79.5%** in dry months to **62.8%** in rainy months, while PA stays between 90% and 97%. Weather standby takes **13.8%** of scheduled hours, more than idle time (12.1%) and over twice all downtime (5.8%).
- **Hydraulics cause 30.5%** of unplanned downtime; the top 3 systems (hydraulic, engine, electrical) cause **66%**. Hydraulic failures also repeat within 30 days **29%** of the time, which suggests fixes that don't address the root cause.
- **Papua: parts logistics, not repair skill:** repair time is similar to other sites, but units wait **20.7 h** for parts per breakdown vs **5.6 h** elsewhere. Waiting for parts is **66%** of its total downtime, and 6 of the top 7 "bad actor" units are at Papua.
- **Sulawesi: maintenance discipline:** only **63%** of PM services are done on time (vs 84–94% at other sites). Across all sites, running past the PM due point raises the breakdown rate **2.6–3.5×**.

## Impact sizing & recommendations
1. **Stock critical hydraulic and engine spares at Papua** (consignment stock or min/max levels). Bringing parts wait down to the other sites' average would recover roughly **2,170 machine-hours per year**.
2. **Enforce PM scheduling at Sulawesi** (lock units out at due hour + 25 h, plus a weekly compliance report). Removing overdue operation would avoid about **45 breakdowns and 750 downtime hours per year**.
3. **Run an RCA programme for hydraulics:** review hose and seal specs and operator practices, and track the repeat-failure rate monthly.
4. **Plan for rain:** schedule PM, training and component change-outs in rainy months to use standby hours productively, and set seasonal UA targets so site performance is judged fairly.

## Tools
SQL (DuckDB) · Python (pandas, NumPy) · reliability metrics (PA, UA, MTBF, MTTR) · Pareto and root cause analysis
