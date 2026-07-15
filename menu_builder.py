"""
Builds variant_map.json for sklep.starfix.eu

For every product in the shop, fetches every variant ("stock") and records:
    SKU (Kod produktu) -> { url: product page URL, hash: "attrId:optId;..." }

Requires: pip install requests

Usage:
    python build_variant_map.py
"""

import requests
import json
import time

SHOP_URL = "https://sklep.starfix.eu"
LOGIN = "admin"           # your admin login
PASSWORD = "chupacabra1234L!"   # do NOT commit this to any public repo

session = requests.Session()

def get_token():
    r = session.post(f"{SHOP_URL}/webapi/rest/auth", auth=(LOGIN, PASSWORD))
    r.raise_for_status()
    token = r.json()["access_token"]
    session.headers.update({"Authorization": f"Bearer {token}"})
    print("Got access token.")

def get_all_products():
    products = []
    page = 1
    while True:
        r = session.get(f"{SHOP_URL}/webapi/rest/products", params={"page": page})
        r.raise_for_status()
        data = r.json()
        products.extend(data["list"])
        print(f"Fetched products page {page}/{data['pages']}")
        if page >= data["pages"]:
            break
        page += 1
        time.sleep(0.2)  # be gentle on the API
    return products

def get_all_categories():
    categories = []
    page = 1
    while True:
        r = session.get(f"{SHOP_URL}/webapi/rest/categories", params={"page": page})
        r.raise_for_status()
        data = r.json()
        categories.extend(data["list"])
        print(f"Fetched categories page {page}/{data['pages']}")
        if page >= data["pages"]:
            break
        page += 1
        time.sleep(0.2)
    return categories

def get_stocks_bulk(stock_ids):
    """Fetch up to 25 stock records per request using the bulk endpoint, with retry on rate limits."""
    results = {}
    for i in range(0, len(stock_ids), 25):
        batch = stock_ids[i:i + 25]
        calls = [
            {
                "id": str(sid),
                "path": f"/webapi/rest/product-stocks/{sid}",
                "method": "GET",
            }
            for sid in batch
        ]

        max_retries = 6
        for attempt in range(max_retries):
            r = session.post(f"{SHOP_URL}/webapi/rest/bulk", json=calls)
            if r.status_code == 429:
                retry_after = r.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else (2 ** attempt) * 2
                print(f"  Rate limited (429). Waiting {wait:.1f}s before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            break
        else:
            raise RuntimeError("Exceeded max retries on bulk endpoint (rate limit).")

        response = r.json()
        # Real shape: {"errors": false, "items": [{"id": "...", "code": 200, "body": {...}}]}
        for item in response.get("items", []):
            if item.get("code") == 200 and isinstance(item.get("body"), dict):
                results[item["id"]] = item["body"]
            else:
                print(f"  Warning: stock {item.get('id')} returned code {item.get('code')}")

        time.sleep(1.0)  # slower pace between batches to avoid hitting the limit again
    return results

def main():
    get_token()
    products = get_all_products()
    print(f"Total products: {len(products)}")

    categories_raw = get_all_categories()
    print(f"Total categories: {len(categories_raw)}")

    # Shoper's categories API exposes no parent-child field at all (confirmed via direct
    # API testing) -- only a "root" 1/0 flag. Since this shop's category tree is small
    # (~22 categories) and rarely changes, the hierarchy is hardcoded here, built directly
    # from the real admin tree. Update this map if you restructure categories later.
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
        "2018": "2017",  # * Groty -> Extreme
        "2019": "2017",  # * Nasadki magnetyczne -> Extreme
        "2020": "2017",  # * Uchwyty magnetyczne -> Extreme
        "2022": "2021",  # - Groty -> PRO
        "2023": "2021",  # - Nasadki magnetyczne -> PRO
        "2024": "2021",  # - Uchwyty magnetyczne -> PRO
    }

    def clean_name(name):
        # strip the admin's "* " / "- " tier markers used only to disambiguate duplicate
        # names in the flat admin list -- the parent folder (Basic/PRO/Extreme) already
        # conveys that distinction in the nested menu.
        return name.lstrip("*- ").strip()

    # Build category lookup: id -> {name, parent_id}
    categories = {}
    for cat in categories_raw:
        cat_id = str(cat["category_id"])
        name = clean_name(cat.get("translations", {}).get("pl_PL", {}).get("name", f"Kategoria {cat_id}"))
        parent_id = CATEGORY_PARENTS.get(cat_id)  # None if not in the map -> top-level
        categories[cat_id] = {"name": name, "parent_id": parent_id, "products": []}

    variant_map = {}
    product_index = []

    for product in products:
        product_id = product["product_id"]
        url = product["translations"]["pl_PL"]["permalink"]
        name = product["translations"]["pl_PL"]["name"]
        base_code = product.get("code", "")
        stock_ids = product.get("options", [])
        cat_id = str(product.get("category_id")) if product.get("category_id") else None

        main_image = product.get("main_image") or {}
        img_url = None
        if main_image.get("gfx_id") and main_image.get("name"):
            img_url = f"{SHOP_URL}/userdata/public/gfx/{main_image['gfx_id']}/{main_image['name']}?overlay=1"

        product_entry = {"name": name, "code": base_code, "url": url, "img": img_url, "category_id": cat_id}
        product_index.append(product_entry)

        if cat_id and cat_id in categories:
            categories[cat_id]["products"].append({"name": name, "url": url, "img": img_url})

        if not stock_ids:
            continue

        stocks = get_stocks_bulk(stock_ids)

        for sid, stock in stocks.items():
            if not isinstance(stock, dict):
                continue
            code = stock.get("code")
            options = stock.get("options")
            if not code or not options:
                continue
            hash_str = ";".join(f"{k}:{v}" for k, v in options.items())
            variant_map[code] = {"url": url, "hash": hash_str, "img": img_url}

        print(f"Product {product_id}: {len(stocks)} variants processed")

    # Build nested menu tree: top-level categories (parent_id None) with children nested under them
    def build_tree(parent_id):
        nodes = []
        for cat_id, cat in categories.items():
            if cat["parent_id"] == parent_id:
                children = build_tree(cat_id)
                # Only include categories that have products (directly or via children)
                if cat["products"] or children:
                    nodes.append({
                        "id": cat_id,
                        "name": cat["name"],
                        "products": cat["products"],
                        "children": children
                    })
        return nodes

    menu_tree = build_tree(None)

    with open("variant_map.json", "w", encoding="utf-8") as f:
        json.dump(variant_map, f, ensure_ascii=False, indent=0)

    with open("products.json", "w", encoding="utf-8") as f:
        json.dump(product_index, f, ensure_ascii=False, indent=0)

    with open("menu.json", "w", encoding="utf-8") as f:
        json.dump(menu_tree, f, ensure_ascii=False, indent=0)

    print(f"\nDone. {len(variant_map)} variant SKUs written to variant_map.json")
    print(f"Done. {len(product_index)} products written to products.json")
    print(f"Done. {len(menu_tree)} top-level categories written to menu.json")

if __name__ == "__main__":
    main()