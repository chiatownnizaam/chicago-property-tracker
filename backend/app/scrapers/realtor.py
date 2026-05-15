"""
Realtor.com scraper.

Realtor.com doesn't expose a fully-public REST endpoint like Redfin's CSV
download, so we scrape the embedded JSON from their search-results HTML page.
Every Realtor.com search page contains a `__NEXT_DATA__` script tag with the
full listing dataset that powers the page — this is what their React app reads
client-side.

This approach is fragile (HTML structure can change) so it's wrapped in
try/except and the ingest pipeline will skip Realtor results if the parse
breaks.
"""
import json
import logging
import re
import time
from datetime import date, datetime
from typing import List, Dict, Optional
from urllib.parse import quote
import httpx
from app.utils.http import get_text

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Cities to search on Realtor.com
TRACKED_CITIES = [
    ("Chicago", "IL"),
    ("Lincolnwood", "IL"),
    ("Skokie", "IL"),
    ("Evanston", "IL"),
    # Sauganash isn't a separate Realtor.com city, but its ZIP codes (60646)
    # surface under Chicago.
]


def _city_search_url(city: str, state: str) -> str:
    slug = f"{city.replace(' ', '-')}_{state}"
    return f"https://www.realtor.com/realestateandhomes-search/{quote(slug)}"


def fetch_realtor_listings_for_city(city: str, state: str) -> List[Dict]:
    """Pull listings from a city search page on Realtor.com."""
    url = _city_search_url(city, state)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        html = get_text(url, headers=headers)
    except (httpx.HTTPError, Exception) as e:
        log.warning(f"Realtor.com request failed for {city} after retries: {e}")
        return []

    # Extract the embedded JSON
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        log.warning(f"Realtor.com: __NEXT_DATA__ block not found for {city}")
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        log.warning(f"Realtor.com JSON parse error for {city}: {e}")
        return []

    # Realtor.com nests its search results in different paths depending on
    # the page version; check the most common locations
    results = (
        _dig(data, "props", "pageProps", "searchResults", "home_search", "results")
        or _dig(data, "props", "pageProps", "properties")
        or _dig(data, "props", "pageProps", "initialReduxState", "searchResults", "properties")
        or []
    )

    return [normalize_realtor_record(r, city) for r in results if r]


def fetch_all_listings() -> List[Dict]:
    """Fetch listings across all tracked cities."""
    all_listings: List[Dict] = []
    for city, state in TRACKED_CITIES:
        log.info(f"Fetching Realtor.com listings for {city}, {state}...")
        listings = fetch_realtor_listings_for_city(city, state)
        all_listings.extend(listings)
        time.sleep(2)  # be polite
    return all_listings


def normalize_realtor_record(raw: Dict, city_fallback: Optional[str] = None) -> Dict:
    """Convert a Realtor.com property record into a normalized listing dict."""
    address = raw.get("location", {}).get("address", {}) if isinstance(raw.get("location"), dict) else {}
    description = raw.get("description", {}) if isinstance(raw.get("description"), dict) else {}
    list_price = raw.get("list_price") or raw.get("price")
    photo_url = None
    if isinstance(raw.get("primary_photo"), dict):
        photo_url = raw["primary_photo"].get("href")
    elif isinstance(raw.get("photos"), list) and raw["photos"]:
        photo_url = raw["photos"][0].get("href") if isinstance(raw["photos"][0], dict) else None

    coordinates = address.get("coordinate", {}) if isinstance(address.get("coordinate"), dict) else {}

    return {
        "source": "realtor",
        "source_listing_id": str(raw.get("property_id") or raw.get("listing_id") or ""),
        "url": f"https://www.realtor.com/realestateandhomes-detail/{raw.get('permalink', '')}" if raw.get("permalink") else None,
        "address": address.get("line", "") or "",
        "city": (address.get("city") or city_fallback or "").strip().title(),
        "state": address.get("state_code") or "IL",
        "zip_code": address.get("postal_code"),
        "latitude": _to_float(coordinates.get("lat")),
        "longitude": _to_float(coordinates.get("lon")),
        "current_price": _to_float(list_price),
        "beds": _to_int(description.get("beds")),
        "baths": _to_float(description.get("baths_consolidated") or description.get("baths")),
        "sqft": _to_float(description.get("sqft")),
        "price_per_sqft": _to_float(description.get("sqft") and list_price and (float(list_price) / float(description["sqft"]))) if description.get("sqft") and list_price else None,
        "year_built": _to_int(description.get("year_built")),
        "property_type": description.get("type"),
        "status": raw.get("status"),
        "days_on_market": _to_int(raw.get("days_on_market")),
        "list_date": _parse_iso_date(raw.get("list_date")) or date.today(),
        "photo_url": photo_url,
        "mls_number": str(raw.get("source", {}).get("listing_id", "")) if isinstance(raw.get("source"), dict) else None,
    }


def _dig(d: Dict, *keys):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _to_float(val) -> Optional[float]:
    try:
        return float(val) if val is not None and val != "" else None
    except (TypeError, ValueError):
        return None


def _to_int(val) -> Optional[int]:
    try:
        f_val = _to_float(val)
        return int(f_val) if f_val is not None else None
    except (TypeError, ValueError):
        return None


def _parse_iso_date(value: Optional[str]):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return None
