"""
Redfin scraper using their public CSV download endpoint.

Redfin provides a "Download all" feature on every search results page that hits
this endpoint and returns CSV of every listing in the search area:

  https://www.redfin.com/stingray/api/gis-csv

This is the same endpoint a logged-out browser uses, so we're not bypassing
any auth. Be respectful: keep request volume low, use a real User-Agent,
and cache between runs.

Region IDs (Redfin's internal `region_id`s) for our tracked municipalities:
  - Chicago: 29470
  - Lincolnwood: 35107
  - Skokie: 35106
  - Sauganash is a Chicago neighborhood (not a separate Redfin region)
"""
import csv
import io
import logging
import time
from datetime import date, datetime
from typing import List, Dict, Optional
import httpx
from app.utils.http import get_text

log = logging.getLogger(__name__)

REDFIN_CSV_URL = "https://www.redfin.com/stingray/api/gis-csv"

REDFIN_REGIONS = {
    "Chicago": {"region_id": 29470, "region_type": 6},     # 6 = city
    "Lincolnwood": {"region_id": 35107, "region_type": 6},
    "Skokie": {"region_id": 35106, "region_type": 6},
    "Evanston": {"region_id": 30866, "region_type": 6},
    # Sauganash — Chicago neighborhood (region_type 1)
    "Sauganash": {"region_id": 27031, "region_type": 1},
}

# Property types: 1 = House, 2 = Condo, 3 = Townhouse, 4 = Multi-family,
# 5 = Land, 6 = Other, 7 = Manufactured, 8 = Co-op
DEFAULT_UIPT = "1,2,3,4"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _build_params(region_id: int, region_type: int) -> dict:
    return {
        "al": 1,
        "market": "chicago",
        "min_stories": 1,
        "num_homes": 350,
        "ord": "redfin-recommended-asc",
        "page_number": 1,
        "region_id": region_id,
        "region_type": region_type,
        "sf": "1,2,3,5,6,7",       # for sale
        "status": 9,                # active listings
        "uipt": DEFAULT_UIPT,
        "v": 8,
    }


def fetch_redfin_listings_for_region(region_id: int, region_type: int) -> List[Dict]:
    """Fetch one region's active listings as a list of dicts."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/csv, */*",
        "Referer": "https://www.redfin.com/",
    }
    try:
        text = get_text(
            REDFIN_CSV_URL,
            params=_build_params(region_id, region_type),
            headers=headers,
        )
    except (httpx.HTTPError, Exception) as e:
        log.warning(f"Redfin request failed for region {region_id} after retries: {e}")
        return []

    if not text or "<html" in text[:200].lower():
        log.warning(f"Redfin returned non-CSV content for region {region_id}")
        return []

    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def fetch_all_listings() -> List[Dict]:
    """Fetch active listings across all tracked regions, with normalization."""
    all_records: List[Dict] = []
    for city_name, region in REDFIN_REGIONS.items():
        log.info(f"Fetching Redfin listings for {city_name}...")
        records = fetch_redfin_listings_for_region(region["region_id"], region["region_type"])
        for r in records:
            all_records.append(normalize_redfin_record(r, city_fallback=city_name))
        time.sleep(2)   # be polite

    return all_records


def normalize_redfin_record(raw: Dict, city_fallback: Optional[str] = None) -> Dict:
    """Convert a Redfin CSV row into a normalized listing dict."""
    def f(*keys: str) -> Optional[str]:
        for k in keys:
            v = raw.get(k)
            if v not in (None, "", "NULL"):
                return v
        return None

    def to_float(val) -> Optional[float]:
        if not val:
            return None
        try:
            return float(str(val).replace(",", "").replace("$", "").strip())
        except (TypeError, ValueError):
            return None

    def to_int(val) -> Optional[int]:
        try:
            f_val = to_float(val)
            return int(f_val) if f_val is not None else None
        except (TypeError, ValueError):
            return None

    return {
        "source": "redfin",
        "source_listing_id": f("PROPERTY ID", "MLS#"),
        "url": f("URL (SEE https://www.redfin.com/buy-a-home/comparative-market-analysis FOR INFO ON PRICING)", "URL"),
        "address": f("ADDRESS") or "",
        "city": (f("CITY") or city_fallback or "").strip().title(),
        "state": f("STATE OR PROVINCE", "STATE") or "IL",
        "zip_code": f("ZIP OR POSTAL CODE", "ZIP"),
        "latitude": to_float(f("LATITUDE")),
        "longitude": to_float(f("LONGITUDE")),
        "current_price": to_float(f("PRICE")),
        "beds": to_int(f("BEDS")),
        "baths": to_float(f("BATHS")),
        "sqft": to_float(f("SQUARE FEET")),
        "price_per_sqft": to_float(f("$/SQUARE FEET")),
        "lot_size": to_float(f("LOT SIZE")),
        "year_built": to_int(f("YEAR BUILT")),
        "property_type": f("PROPERTY TYPE"),
        "status": f("STATUS"),
        "days_on_market": to_int(f("DAYS ON MARKET")),
        "list_date": _parse_redfin_date(f("SOLD DATE")) or date.today(),
        "mls_number": f("MLS#"),
    }


def _parse_redfin_date(value: Optional[str]):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except (ValueError, TypeError):
            continue
    return None
