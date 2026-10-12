# Devin Lee: Data Analytics Portfolio

Live site: **https://devinlee14.github.io**

Data analyst in Jakarta with 3+ years in operational, commercial and performance analytics (heavy equipment, e-commerce, oil & gas). This repo holds the portfolio website and the full code for each project.

| Project | Data | What it shows |
|---|---|---|
| [Hotel utility data pipeline & ESG reporting](projects/hotel-esg-data-pipeline) | Simulated, 40 hotels | Python data-quality pipeline: validation, bill reconciliation (incl. offset billing cycles), gap-filling, audit logs, Scope 1 & 2 emissions. Scored against a hidden answer key: **99.5% of errors caught, 0 false corrections**. |
| [E-commerce growth & customer retention](projects/ecommerce-customer-analytics) | Real, Olist (98k orders) | SQL (DuckDB): window-function KPIs, cohort retention, RFM, category Pareto, repeat-purchase drivers with a significance test. |
| [Delivery experience root cause analysis](projects/delivery-experience-rca) | Real, Olist (95k deliveries) | Python: fulfilment-stage decomposition and logistic regression. **Late orders have 13.9× the odds of a 1–2★ review**; carrier transit is the main source of delay. |
| [Heavy equipment availability & downtime](projects/equipment-utilization-rca) | Simulated, 48-unit fleet | SQL: PA/UA, MTBF/MTTR, downtime Pareto, PM compliance vs failure rate, repeat failures. Sizes the recoverable hours for each root cause. |

## Reproduce
```bash
pip install pandas numpy duckdb statsmodels
# Hotel ESG
cd projects/hotel-esg-data-pipeline && python src/generate_data.py && python src/pipeline.py && python src/evaluate.py
# E-commerce (downloads the public Olist data first)
cd projects/ecommerce-customer-analytics && python src/get_data.py && python src/run_analysis.py
# Delivery RCA
cd projects/delivery-experience-rca && python src/get_data.py && python src/analysis.py
# Equipment
cd projects/equipment-utilization-rca && python src/generate_data.py && python src/run_analysis.py
```
Each project's `src/build_site_data.py` (or `analysis.py`) writes the JSON in `assets/data/` that powers the website charts.

## Site
Plain HTML, CSS and JavaScript (no build step), with Chart.js for interactive charts and Lenis for smooth scrolling. Fonts: Bricolage Grotesque and IBM Plex Sans (SIL OFL).

Contact: lee.devinlee14@gmail.com · [LinkedIn](https://www.linkedin.com/in/devin-lee-5566b6206/)
