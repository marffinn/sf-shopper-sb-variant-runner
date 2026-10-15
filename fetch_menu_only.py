import requests
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()

SHOP_URL = "https://sklep.starfix.eu"
session = requests.Session()

# Shoper's API doesn't expose parent-child relationships; hierarchy is hardcoded.
# Update this map when you add or restructure categories.
CATEGORY_PARENTS = {
    "1987": "1986",  # Ogólne -> Zamocowania
    "1988": "1986",  # Ramowe -> Zamocowania
    "1989": "1986",  # Lekkie -> Zamocowania
    "1990": "1986",  # Do termoizolacji -> Zamocowania
    "2013": "2012",  # Basic -> Akcesoria do wkrętarek
    "2017": "2012",  # Extreme -> Akcesoria do wkrętarek
    "2021": "2012",  # PRO -> Akcesoria do wkrętarek
    "2014": "2013",  # Groty -> Basic
    "2015": "2013",  # Nasadki magnetyczne -> Basic
    "2016": "2013",  # Uchwyty magnetyczne -> Basic
    "2018": "2017",  # Groty -> Extreme
    "2019": "2017",  # Nasadki magnetyczne -> Extreme
    "2020": "2017",  # Uchwyty magnetyczne -> Extreme
    "2022": "2021",  # Groty -> PRO
    "2023": "2021",  # Nasadki magnetyczne -> PRO
    "2024": "2021",  # Uchwyty magnetyczne -> PRO
}

TOP_LEVEL_ORDER = [
    "Zamocowania", "Łączniki", "Chemia budowlana",
    "Wiertła i dłuta", "Elementy złączne", "Akcesoria do wkrętarek",
]


def fetch_all(endpoint):
    items, page = [], 1
    while True:
        data = session.get(f"{SHOP_URL}/webapi/rest/{endpoint}", params={"page": page}).json()
        items.extend(data["list"])
        if page >= data["pages"]:
            break
        page += 1
        time.sleep(0.2)
    return items


def main():
    token = session.post(
        f"{SHOP_URL}/webapi/rest/auth",
        auth=(os.getenv("SHOP_LOGIN"), os.getenv("SHOP_PASSWORD"))
    ).json()["access_token"]
    session.headers["Authorization"] = f"Bearer {token}"

    # Build category map
    categories = {}
    for cat in fetch_all("categories"):
        cat_id = str(cat["category_id"])
        trans = cat.get("translations", {}).get("pl_PL", {})
        if trans.get("active") != "1":
            continue
        categories[cat_id] = {
            "name": trans.get("name", "").lstrip("*- ").strip(),
            "url": trans.get("permalink", ""),
            "parent_id": CATEGORY_PARENTS.get(cat_id),
            "products": [],
        }

    # Populate categories with products
    for product in fetch_all("products"):
        trans = product["translations"]["pl_PL"]
        url, name = trans["permalink"], trans["name"]
        if "\r" in url or "\n" in name:
            continue  # skip corrupted permalinks
        cat_id = str(product["category_id"]) if product.get("category_id") else None
        if not cat_id or cat_id not in categories:
            continue
        img = product.get("main_image") or {}
        img_url = (
            f"{SHOP_URL}/userdata/public/gfx/{img['gfx_id']}/{img['name']}?overlay=1"
            if img.get("gfx_id") and img.get("name") else None
        )
        categories[cat_id]["products"].append({
            "name": " ".join(name.split()),
            "url": url,
            "img": img_url,
        })

    # Build nested tree
    def build_tree(parent_id):
        nodes = []
        for cat_id, cat in categories.items():
            if cat["parent_id"] != parent_id:
                continue
            children = build_tree(cat_id)
            if cat["products"] or children:
                nodes.append({
                    "id": cat_id,
                    "name": cat["name"],
                    "url": cat["url"],
                    "products": cat["products"],
                    "children": children,
                })
        return nodes

    menu = build_tree(None)
    menu.sort(key=lambda n: TOP_LEVEL_ORDER.index(n["name"]) if n["name"] in TOP_LEVEL_ORDER else len(TOP_LEVEL_ORDER))

    with open("menu.json", "w", encoding="utf-8") as f:
        json.dump(menu, f, ensure_ascii=False, indent=2)

    print(f"Done. {len(menu)} top-level categories written to menu.json")


if __name__ == "__main__":
    main()
