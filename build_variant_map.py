"""
Builds variant_map.json for sklep.starfix.eu

For every product in the shop, fetches every variant ("stock") and records:
    SKU (Kod produktu) -> { url: product page URL, hash: "attrId:optId;..." }

Requires: pip install requests

Usage:
    python build_variant_map.py
"""

import os
import requests
import json
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

SHOP_URL = os.getenv("SHOP_URL", "https://sklep.starfix.eu")
LOGIN = os.getenv("SHOP_LOGIN")
PASSWORD = os.getenv("SHOP_PASSWORD")

if not LOGIN or not PASSWORD:
    raise ValueError("SHOP_LOGIN and SHOP_PASSWORD environment variables must be set in the .env file")

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

    variant_map = {}
    product_index = []

    for product in products:
        product_id = product["product_id"]
        url = product["translations"]["pl_PL"]["permalink"]
        name = product["translations"]["pl_PL"]["name"]
        base_code = product.get("code", "")
        stock_ids = product.get("options", [])

        # Extract product main image if available
        main_image = product.get("main_image")
        image_url = None
        if isinstance(main_image, dict):
            gfx_id = main_image.get("gfx_id")
            name_file = main_image.get("name")
            if gfx_id and name_file:
                image_url = f"https://sklep.starfix.eu/environment/cache/images/productGfx_{gfx_id}_100_100/{name_file}"

        product_index.append({"name": name, "code": base_code, "url": url, "image": image_url})

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
            variant_map[code] = {"url": url, "hash": hash_str, "image": image_url}

        print(f"Product {product_id}: {len(stocks)} variants processed")

    with open("variant_map.json", "w", encoding="utf-8") as f:
        json.dump(variant_map, f, ensure_ascii=False, indent=0)

    with open("products.json", "w", encoding="utf-8") as f:
        json.dump(product_index, f, ensure_ascii=False, indent=0)

    print(f"\nDone. {len(variant_map)} variant SKUs written to variant_map.json")
    print(f"Done. {len(product_index)} products written to products.json")

if __name__ == "__main__":
    main()