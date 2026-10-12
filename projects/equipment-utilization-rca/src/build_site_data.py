"""Summarise SQL outputs + impact sizing into JSON for the portfolio page."""
from pathlib import Path
import json
import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
O = ROOT / "outputs"
SITE = ROOT.parents[1] / "assets" / "data"
con = duckdb.connect()
con.execute(f"SET file_search_path = '{ROOT}'")
con.execute((ROOT / "sql" / "00_staging.sql").read_text())

fleet = con.sql("""SELECT 100*(1-SUM(downtime_h)/SUM(scheduled_h)) pa,
                          100*SUM(operating_h)/(SUM(scheduled_h)-SUM(downtime_h)) ua,
                          SUM(operating_h) op FROM daily""").df().iloc[0]
season = con.sql("""SELECT site, month(date) m, 100*SUM(operating_h)/(SUM(scheduled_h)-SUM(downtime_h)) ua,
                           100*(1-SUM(downtime_h)/SUM(scheduled_h)) pa
                    FROM daily GROUP BY ALL ORDER BY site, m""").df()
k = pd.read_csv(O / "01_fleet_kpis.csv")
par = pd.read_csv(O / "03_downtime_pareto.csv")
mt = pd.read_csv(O / "04_mttr_decomposition.csv").set_index("site")
pmc = pd.read_csv(O / "05_pm_compliance_vs_failures.csv").set_index("site")
rep = pd.read_csv(O / "06_repeat_failures.csv")
bad = pd.read_csv(O / "07_bad_actors.csv")

# impact 1: Papua parts wait brought to the average of the other sites
others = mt.drop(index="Site D - Papua").waiting_parts_h.mean()
papua_saved_h = (mt.loc["Site D - Papua", "waiting_parts_h"] - others) * mt.loc["Site D - Papua", "breakdowns"]
# impact 2: Sulawesi overdue hours run at the on-schedule failure rate
sul = pmc.loc["Site C - Sulawesi"]
sul_overdue_h = con.sql("SELECT SUM(operating_h) FROM daily WHERE site='Site C - Sulawesi'").fetchone()[0] \
    * sul.pct_hours_overdue / 100
avoid_bd = sul_overdue_h * (sul.bd_per_1000h_overdue - sul.bd_per_1000h_on_schedule) / 1000
mttr_sul = con.sql("SELECT AVG(duration_h) FROM events WHERE event_type='Breakdown' AND site='Site C - Sulawesi'").fetchone()[0]

split = con.sql("SELECT 100*SUM(operating_h)/SUM(scheduled_h) op, 100*SUM(idle_h)/SUM(scheduled_h) idle, 100*SUM(standby_weather_h)/SUM(scheduled_h) standby, 100*SUM(downtime_h)/SUM(scheduled_h) down FROM daily").df().iloc[0].round(1).to_dict()
data = {
    "split": split,
    "kpi": {"units": 48, "sites": 4, "unit_days": 17520, "pa": round(fleet.pa, 1), "ua": round(fleet.ua, 1),
            "breakdowns": int(par.breakdowns.sum()), "hydraulic_share": float(par.iloc[0].cumulative_pct),
            "top3_share": float(par.iloc[2].cumulative_pct),
            "papua_parts_share": float(mt.loc["Site D - Papua", "parts_share_pct"]),
            "papua_parts_wait": float(mt.loc["Site D - Papua", "waiting_parts_h"]),
            "others_parts_wait": round(others, 1), "papua_saved_h": round(papua_saved_h),
            "sulawesi_compliance": float(sul.pm_compliance_pct),
            "overdue_ratio_min": round(float((pmc.bd_per_1000h_overdue / pmc.bd_per_1000h_on_schedule).min()), 1),
            "overdue_ratio_max": round(float((pmc.bd_per_1000h_overdue / pmc.bd_per_1000h_on_schedule).max()), 1),
            "sulawesi_avoidable_bd": round(avoid_bd), "sulawesi_avoidable_h": round(avoid_bd * mttr_sul),
            "hydraulic_repeat": float(rep.set_index("system").loc["Hydraulic", "repeat_pct"]),
            "rainy_ua": round(season[season.ua < 70].ua.mean(), 1), "dry_ua": round(season[season.ua >= 70].ua.mean(), 1)},
    "season": {s: {"ua": g.ua.round(1).tolist(), "pa": g.pa.round(1).tolist()} for s, g in season.groupby("site")},
    "pareto": par.to_dict("list"),
    "mttr": mt.reset_index()[["site", "repair_h", "waiting_parts_h", "waiting_mechanic_h"]].to_dict("list"),
    "pm": pmc.reset_index()[["site", "pm_compliance_pct", "pct_hours_overdue", "bd_per_1000h_on_schedule",
                             "bd_per_1000h_overdue"]].to_dict("records"),
    "bad": bad[["unit_id", "site", "model", "breakdowns", "downtime_h"]].to_dict("records"),
}
(SITE / "equipment.json").write_text(json.dumps(data, indent=1))
print(json.dumps(data["kpi"], indent=1))
