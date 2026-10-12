"""
Generate a SIMULATED heavy-equipment fleet dataset (48 units, 4 sites, 2025).

Operational fleet data is confidential, so this script creates a realistic
stand-in that mirrors the data a mining / construction contractor collects:
  units.csv             fleet master (model, site, age)
  daily_operations.csv  scheduled / operating / idle / standby / downtime hours per unit-day
  downtime_events.csv   every breakdown and preventive maintenance (PM) job, with
                        affected system and time split into repair / waiting parts / waiting mechanic
  pm_services.csv       PM services performed vs due hour-meter (every 250 h)

Causal effects built in (the analysis has to discover them):
  * overdue PM raises the breakdown rate; one site has poor PM discipline
  * one remote site waits much longer for spare parts
  * older units fail more often; rainy season adds standby (not downtime)
Run:  python src/generate_data.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

rng = np.random.default_rng(7)
OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)

SITES = {  # pm_compliance, parts_wait_median_h, rainy_months
    "Site A - Kalimantan": (0.93, 10, [11, 12, 1, 2, 3]),
    "Site B - Sumatra": (0.90, 8, [10, 11, 12, 1]),
    "Site C - Sulawesi": (0.68, 12, [12, 1, 2, 3, 4]),
    "Site D - Papua": (0.88, 46, [1, 2, 3, 4, 5, 6]),
}
MODELS = {  # type, base breakdowns per 1,000 operating h
    "EX-200 Excavator": ("Excavator", 2.0),
    "EX-360 Excavator": ("Excavator", 2.3),
    "WL-50 Wheel Loader": ("Wheel Loader", 1.7),
    "DT-60 Dump Truck": ("Dump Truck", 2.1),
}
SYSTEMS = {  # share of failures, median repair hours
    "Hydraulic": (0.32, 7), "Engine": (0.18, 12), "Electrical": (0.16, 4),
    "Undercarriage / Tyres": (0.14, 10), "Cooling": (0.10, 5), "Attachment / Bucket": (0.10, 6),
}
SCHED_H = 20.0       # two 10-hour shifts
PM_INTERVAL = 250    # hour-meter hours

units = []
for i in range(48):
    site = list(SITES)[i % 4]
    model = list(MODELS)[(i // 4) % 4]
    units.append(dict(unit_id=f"U-{i + 1:03d}", model=model, unit_type=MODELS[model][0], site=site,
                      commission_year=int(rng.choice([2017, 2019, 2020, 2021, 2022, 2023, 2024])),
                      hour_meter_start=int(rng.integers(2000, 26000))))
units = pd.DataFrame(units)
units.to_csv(OUT / "units.csv", index=False)

days = pd.date_range("2025-01-01", "2025-12-31", freq="D")
ops, events, pms = [], [], []
eid = 0
for u in units.itertuples():
    compliance, parts_med, rainy = SITES[u.site]
    base_rate = MODELS[u.model][1] / 1000 * (1 + 0.07 * (2025 - u.commission_year))
    hm = float(u.hour_meter_start)
    next_pm = (hm // PM_INTERVAL + 1) * PM_INTERVAL
    pm_delay = 0.0 if rng.random() < compliance else rng.uniform(60, 220)
    down_carry = 0.0                       # downtime hours carried into following days
    for d in days:
        rain = d.month in rainy
        standby = SCHED_H * (rng.uniform(0.15, 0.35) if rain else rng.uniform(0.02, 0.10))
        down = min(down_carry, SCHED_H)
        down_carry -= down
        avail = SCHED_H - down
        standby = min(standby, avail)
        op_target = (avail - standby) * rng.uniform(0.78, 0.92)
        op = 0.0
        # simulate the day in blocks of up to 4 operating hours; each block can fail
        remaining = op_target
        while remaining > 0 and down_carry == 0:
            block = min(4.0, remaining)
            overdue = hm > next_pm + 25
            rate = base_rate * (2.6 if overdue else 1.0)
            if rng.random() < 1 - np.exp(-rate * block):
                # breakdown
                sys_ = rng.choice(list(SYSTEMS), p=[v[0] for v in SYSTEMS.values()])
                repair = rng.lognormal(np.log(SYSTEMS[sys_][1]), 0.5)
                parts = rng.lognormal(np.log(parts_med), 0.6) if rng.random() < 0.45 else 0.0
                mech = rng.lognormal(np.log(1.5), 0.5)
                start = d + pd.Timedelta(hours=6 + (op_target - remaining) + block / 2)
                total = repair + parts + mech
                eid += 1
                events.append(dict(event_id=f"EV-{eid:05d}", unit_id=u.unit_id, event_type="Breakdown",
                                   system=sys_, start_time=start.round("min"),
                                   end_time=(start + pd.Timedelta(hours=total)).round("min"),
                                   repair_h=round(repair, 2), waiting_parts_h=round(parts, 2),
                                   waiting_mechanic_h=round(mech, 2), hour_meter=round(hm, 1),
                                   pm_overdue=bool(overdue)))
                op += block / 2
                hm += block / 2
                down_carry = total
                today_down = min(down_carry, SCHED_H - down - op - standby)
                down += max(today_down, 0)
                down_carry -= max(today_down, 0)
                break
            op += block
            hm += block
            remaining -= block
        # preventive maintenance when due (+ any site-specific delay)
        if down_carry == 0 and hm >= next_pm + pm_delay:
            dur = rng.uniform(6, 10)
            eid += 1
            start = d + pd.Timedelta(hours=18)
            events.append(dict(event_id=f"EV-{eid:05d}", unit_id=u.unit_id, event_type="Preventive maintenance",
                               system="PM service", start_time=start.round("min"),
                               end_time=(start + pd.Timedelta(hours=dur)).round("min"),
                               repair_h=round(dur, 2), waiting_parts_h=0.0, waiting_mechanic_h=0.0,
                               hour_meter=round(hm, 1), pm_overdue=False))
            pms.append(dict(unit_id=u.unit_id, service_date=d.date(), due_hour_meter=next_pm,
                            actual_hour_meter=round(hm, 1)))
            down_carry = dur
            next_pm = (hm // PM_INTERVAL + 1) * PM_INTERVAL
            pm_delay = 0.0 if rng.random() < compliance else rng.uniform(60, 220)
        idle = max(SCHED_H - down - standby - op, 0)   # available, not weather-bound, not operating
        ops.append(dict(date=d.date(), unit_id=u.unit_id, scheduled_h=SCHED_H, operating_h=round(op, 2),
                        idle_h=round(idle, 2), standby_weather_h=round(standby, 2), downtime_h=round(down, 2),
                        hour_meter_end=round(hm, 1)))

pd.DataFrame(ops).to_csv(OUT / "daily_operations.csv", index=False)
pd.DataFrame(events).to_csv(OUT / "downtime_events.csv", index=False)
pd.DataFrame(pms).to_csv(OUT / "pm_services.csv", index=False)
ev = pd.DataFrame(events)
print(len(ops), "unit-days |", len(ev), "events")
print(ev.event_type.value_counts().to_string())
