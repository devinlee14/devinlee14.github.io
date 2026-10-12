"""Download the public Olist Brazilian E-Commerce dataset (CC BY-NC-SA 4.0).

Source: https://github.com/olist/work-at-olist-data (also on Kaggle as
"Brazilian E-Commerce Public Dataset by Olist"). ~100k orders, 2016-2018.
"""
from pathlib import Path
from urllib.request import urlretrieve

BASE = "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/"
FILES = ["olist_orders_dataset", "olist_order_items_dataset", "olist_customers_dataset",
         "olist_order_payments_dataset", "olist_order_reviews_dataset", "olist_products_dataset",
         "olist_sellers_dataset", "product_category_name_translation"]
OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)
for f in FILES:
    dest = OUT / f"{f}.csv"
    if not dest.exists():
        print("downloading", f)
        urlretrieve(BASE + f + ".csv", dest)
print("done ->", OUT)
