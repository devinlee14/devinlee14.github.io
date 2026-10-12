"""Add data-id (Indonesian) attributes to every translatable element.

Run from the repo root after editing page text:  python tools/apply_i18n.py
"""
import re, sys, html
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString
sys.path.insert(0, str(Path(__file__).parent))
from i18n_id import ID

TAGS = {"a", "p", "li", "dt", "dd", "h1", "h2", "h3", "span", "small", "strong", "th", "button"}
PAGES = ["index.html"] + [f"projects/{p}/index.html" for p in
         ["hotel-esg-data-pipeline", "ecommerce-customer-analytics", "delivery-experience-rca", "equipment-utilization-rca"]]

def candidates(soup):
    out = []
    for el in soup.body.find_all(True):
        if el.name not in TAGS: continue
        if el.find_parent(["pre", "script", "svg"]) or (el.find_parent("table") and el.name != "th"): continue
        if el.find(["p", "li", "ul", "ol", "div", "h1", "h2", "h3", "dl"]): continue
        if any(getattr(p, "attrs", {}).get("data-cand") for p in el.parents): continue
        txt = el.get_text("", strip=False)
        if not re.search(r"[A-Za-z]{2}", txt): continue
        el["data-cand"] = "1"
        out.append(el)
    return out

missing = []
for page in PAGES:
    soup = BeautifulSoup(Path(page).read_text(), "html.parser")
    for el in soup.find_all(attrs={"data-id": True}):
        del el["data-id"]
    n = 0
    for el in candidates(soup):
        key = re.sub(r"\s+", " ", el.get_text("")).strip()
        if key not in ID:
            missing.append((page, key)); continue
        val = ID[key]
        if el.find(["svg", "i"]):          # keep the icon, swap only the text
            text_nodes = [t for t in el.find_all(string=True, recursive=False) if t.strip()]
            inner = el.decode_contents()
            for t in text_nodes:
                inner = inner.replace(html.escape(t.strip(), quote=False), val, 1)
            val = inner
        if val == el.decode_contents().strip():
            continue
        el["data-id"] = val
        n += 1
    for el in soup.find_all(attrs={"data-cand": True}):
        del el["data-cand"]
    Path(page).write_text(str(soup))
    print(f"{page}: {n} translated")
print("\nNot translated (kept in English):")
for p, k in missing:
    print(" ", p.split('/')[1] if '/' in p else p, "|", k[:90])
