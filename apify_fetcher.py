import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
APIFY_ACTOR_ID = "pratikdani~tiktok-shop-search-scraper"
APIFY_BASE_URL = f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}"

MOCK_PRODUCTS = [
    {"title": "7 Chakra Healing Bracelet Natural Stone", "price": "$24.99", "url": "https://www.tiktok.com/@healingcrystals/video/example1", "rating": "4.8", "sales": "1.2K", "seller_name": "HealingCrystals"},
    {"title": "Spiritual Chakra Balance Beaded Bracelet", "price": "$19.99", "url": "https://www.tiktok.com/@spiritualshop/video/example2", "rating": "4.6", "sales": "890", "seller_name": "SpiritualShop"},
    {"title": "Handmade Gemstone Seven Chakra Yoga Bracelet", "price": "$29.99", "url": "https://www.tiktok.com/@yogajewelry/video/example3", "rating": "4.9", "sales": "2.1K", "seller_name": "YogaJewelry"},
    {"title": "Natural Stone Chakra Healing Energy Bracelet", "price": "$22.99", "url": "https://www.tiktok.com/@gemstonehub/video/example4", "rating": "4.5", "sales": "650", "seller_name": "GemstoneHub"},
    {"title": "Meditation Chakra Beaded Bracelet for Men Women", "price": "$18.99", "url": "https://www.tiktok.com/@mindfulshop/video/example5", "rating": "4.7", "sales": "1.5K", "seller_name": "MindfulShop"},
]


def _apify_start_run(keyword: str, country_code: str = "US", limit: int = 10) -> str | None:
    """Start an Apify actor run. Returns run_id or None."""
    print(f"[apify] starting run: keyword={keyword}, country={country_code}")
    try:
        resp = requests.post(
            f"{APIFY_BASE_URL}/runs",
            params={"token": APIFY_API_TOKEN, "timeout": 300, "maxItems": limit},
            json={
                "keyword": keyword,
                "country_code": country_code,
                "limit": limit,
                "page": 1,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        run_id = data.get("data", {}).get("id")
        if not run_id:
            print(f"[apify] no run_id in response: {data}")
            return None
        print(f"[apify] run started: {run_id}")
        return run_id
    except Exception as e:
        print(f"[apify] start run failed: {e}")
        return None


def _apify_poll_run(run_id: str) -> tuple[bool, str]:
    """Poll until the run finishes. Returns (ok, dataset_id)."""
    poll_url = f"{APIFY_BASE_URL}/runs/{run_id}"
    MAX_POLLS = 120  # ~6 min at 3s intervals
    for i in range(MAX_POLLS):
        try:
            resp = requests.get(
                poll_url,
                params={"token": APIFY_API_TOKEN},
                timeout=15,
            )
            resp.raise_for_status()
            run_data = resp.json().get("data", {})
            status = run_data.get("status", "")
            dataset_id = run_data.get("defaultDatasetId", "")
            if i % 5 == 0:
                print(f"[apify] poll {i}: status={status}")
            if status == "SUCCEEDED":
                print(f"[apify] run {run_id} SUCCEEDED after {i * 3}s")
                return True, dataset_id
            elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                print(f"[apify] run {run_id} {status}")
                return False, ""
            time.sleep(3)
        except Exception as e:
            print(f"[apify] poll error ({i}): {e}")
            time.sleep(3)
    print(f"[apify] run {run_id} timed out after {MAX_POLLS * 3}s")
    return False, ""


def _apify_fetch_dataset(dataset_id: str, limit: int = 10) -> list[dict]:
    """Fetch dataset items from a completed run by dataset ID."""
    print(f"[apify] fetching dataset {dataset_id}")
    try:
        resp = requests.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items",
            params={"token": APIFY_API_TOKEN, "format": "json", "limit": limit},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[apify] fetch dataset failed: {e}")
        return []


def search_products_apify(keyword: str, country_code: str = "US", limit: int = 10,
                         use_mock: bool = False) -> list[dict]:
    """
    Search TikTok Shop products via Apify (async start → poll → fetch).

    When use_mock=True or when the API returns an empty result, returns MOCK_PRODUCTS instead.

    Returns: [{"title": str, "price": str, "url": str, "rating": str, "sales": str, "seller_name": str}, ...]
    """
    print(f"[apify] keyword: {keyword}, country: {country_code}, limit: {limit}, use_mock={use_mock}")

    if use_mock:
        print("[apify] using mock data")
        return MOCK_PRODUCTS[:limit]

    if not APIFY_API_TOKEN:
        print("[apify] error: APIFY_API_TOKEN not set in .env")
        return []

    run_id = _apify_start_run(keyword, country_code, limit)
    if not run_id:
        return []

    ok, dataset_id = _apify_poll_run(run_id)
    if not ok:
        return []

    if not dataset_id:
        print("[apify] no dataset_id from run — 该关键词在 TikTok Shop 无结果，建议换更通用的关键词")
        return []

    data = _apify_fetch_dataset(dataset_id, limit)

    if not data:
        print("[apify] empty dataset — 该关键词在 TikTok Shop 无结果，建议换更通用的关键词")
        return []

    print(f"[apify] got {len(data)} raw items")

    output = []
    for item in data[:limit]:
        product_id = item.get("product_id", "")
        seller = item.get("seller") or {}
        output.append({
            "title": item.get("product_title") or item.get("product_name", ""),
            "price": item.get("real_price") or item.get("avg_price") or item.get("min_price") or item.get("max_price") or "-",
            "url": f"https://www.tiktok.com/shop/pdp/{product_id}" if product_id else "",
            "rating": item.get("product_rating", ""),
            "sales": item.get("total_sale_cnt", ""),
            "seller_name": seller.get("seller_name", "") if isinstance(seller, dict) else "",
        })

    print(f"[apify] returning {len(output)} products")
    return output


if __name__ == "__main__":
    results = search_products_apify("yoga pants", country_code="US", limit=5)
    print()
    print("=== RESULTS ===")
    print(f"Total: {len(results)} products")
    for i, p in enumerate(results[:3]):
        print(f"{i+1}. {p['title']}")
        print(f"   Price: {p['price']}")
        print(f"   URL: {p['url']}")
        print(f"   Rating: {p['rating']} | Sales: {p['sales']} | Seller: {p['seller_name']}")
        print()
