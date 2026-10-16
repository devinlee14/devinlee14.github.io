"""Run every SQL file in sql/ with DuckDB and save each result to outputs/.

Run from the project folder:  python src/run_analysis.py
"""
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]
con = duckdb.connect()
con.execute(f"SET file_search_path = '{ROOT}'")
for sql_file in sorted((ROOT / "sql").glob("*.sql")):
    sql = sql_file.read_text()
    if sql_file.name.startswith("00_"):
        con.execute(sql)
        continue
    df = con.sql(sql).df()
    df.to_csv(ROOT / "outputs" / f"{sql_file.stem}.csv", index=False)
    print(f"\n== {sql_file.stem} ({len(df)} rows)\n{df.head(12).to_string(index=False)}")
