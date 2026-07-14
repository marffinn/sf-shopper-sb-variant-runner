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
import os

def load_dotenv():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(script_dir, ".env")
    if os.path.exists(dotenv_path):
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    os.environ[key] = val

load_dotenv()

SHOP_URL = os.environ.get("SHOP_URL", "https://sklep.starfix.eu")
LOGIN = os.environ.get("SHOP_LOGIN")
PASSWORD = os.environ.get("SHOP_PASSWORD")

if not LOGIN or not PASSWORD:
    raise ValueError("SHOP_LOGIN and SHOP_PASSWORD environment variables must be set in .env")

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
        time.sleep(0.2)
    return products

def get_stocks_bulk(stock_ids):
    """Fetch up to 25 stock records per request using the bulk endpoint."""
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
        r = session.post(f"{SHOP_URL}/webapi/rest/bulk", json=calls)
        r.raise_for_status()
        response = r.json()
        for item in response.get("items", []):
            if item.get("code") == 200 and isinstance(item.get("body"), dict):
                results[item["id"]] = item["body"]
            else:
                print(f"  Warning: stock {item.get('id')} returned code {item.get('code')}")
        time.sleep(2)
    return results

def main():
    get_token()
    products = get_all_products()
    print(f"Total products: {len(products)}")

    variant_map = {}

    for product in products:
        product_id = product["product_id"]
        url = product["translations"]["pl_PL"]["permalink"]
        stock_ids = product.get("options", [])
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
            variant_map[code] = {"url": url, "hash": hash_str}

        print(f"Product {product_id}: {len(stocks)} variants processed")

    with open("variant_map.json", "w", encoding="utf-8") as f:
        json.dump(variant_map, f, ensure_ascii=False, indent=0)

    print(f"\nDone. {len(variant_map)} variant SKUs written to variant_map.json")

if __name__ == "__main__":
    main()