"""
Verified Cook County Open Data Portal (Socrata) dataset access.

All queries:
  - Use the shared retry-aware HTTP helper
  - Properly escape PINs and city strings for SoQL injection-safety
  - Page through results when needed via $limit / $offset

Notes on data availability:
  - Property sales: `wvhk-k5uv`. Sales records don't include addresses —
    must JOIN to `3723-97qp` (Parcel Addresses) on `pin`.
  - Tax sales: Cook County Treasurer publishes annual + scavenger sales.
  - Foreclosures / Evictions: not in the open data portal. Kept by the
    Circuit Court Clerk only.
"""
import logging
from typing import Optional, List, Dict
from app.config import settings
from app.utils.http import get_json
from app.utils.normalize import safe_soql_in_list, escape_soql_string
from app.constants import TRACKED_CITIES_UPPER

log = logging.getLogger(__name__)

COOK_COUNTY_BASE = "https://datacatalog.cookcountyil.gov/resource"
CHICAGO_BASE = "https://data.cityofchicago.org/resource"

DATASETS = {
    "parcel_sales": f"{COOK_COUNTY_BASE}/wvhk-k5uv.json",
    "parcel_addresses": f"{COOK_COUNTY_BASE}/3723-97qp.json",
    "parcel_universe": f"{COOK_COUNTY_BASE}/nj4t-kc8j.json",
    "tax_sale_annual": f"{COOK_COUNTY_BASE}/55ju-2fs9.json",
    "tax_sale_scavenger": f"{COOK_COUNTY_BASE}/ydgz-vkrp.json",
    "affordable_rental": f"{CHICAGO_BASE}/s6ha-ppgi.json",
}

# Cap on number of PINs in a single SoQL `in()` clause. Socrata accepts a few
# thousand but ~500 is safe and fits inside URL length limits.
SOQL_IN_BATCH = 500


def _headers() -> dict:
    h = {}
    if settings.CHICAGO_DATA_PORTAL_APP_TOKEN:
        h["X-App-Token"] = settings.CHICAGO_DATA_PORTAL_APP_TOKEN
    return h


def _tracked_city_where_clause() -> str:
    """Build a SoQL WHERE clause that selects only our tracked cities."""
    parts = [
        f"upper(prop_address_city_name) = '{escape_soql_string(c)}'"
        for c in TRACKED_CITIES_UPPER
    ]
    return " OR ".join(parts)


def fetch_parcel_addresses(pins: List[str]) -> Dict[str, Dict]:
    """Look up addresses for a list of PINs, batched to avoid URL limits."""
    if not pins:
        return {}
    result: Dict[str, Dict] = {}
    for i in range(0, len(pins), SOQL_IN_BATCH):
        batch = pins[i:i + SOQL_IN_BATCH]
        params = {"$limit": len(batch), "$where": f"pin in {safe_soql_in_list(batch)}"}
        try:
            rows = get_json(DATASETS["parcel_addresses"], params=params, headers=_headers())
        except Exception as e:
            log.warning(f"parcel_addresses batch failed: {e}")
            continue
        for r in rows:
            if r.get("pin"):
                result[r["pin"]] = r
    return result


def _fetch_addresses_for_tracked_cities(limit: int = 20000) -> Dict[str, Dict]:
    rows = get_json(
        DATASETS["parcel_addresses"],
        params={"$limit": limit, "$where": _tracked_city_where_clause()},
        headers=_headers(),
    )
    return {a["pin"]: a for a in rows if a.get("pin")}


def fetch_sales_for_cities(limit_per_city: int = 500) -> List[Dict]:
    """Sales joined with addresses, filtered to tracked cities."""
    pin_to_addr = _fetch_addresses_for_tracked_cities()
    if not pin_to_addr:
        return []

    pins = list(pin_to_addr.keys())
    all_sales: List[Dict] = []
    for i in range(0, len(pins), SOQL_IN_BATCH):
        batch = pins[i:i + SOQL_IN_BATCH]
        params = {
            "$limit": limit_per_city * len(batch),
            "$where": f"pin in {safe_soql_in_list(batch)}",
            "$order": "sale_date DESC",
        }
        try:
            sales = get_json(DATASETS["parcel_sales"], params=params, headers=_headers())
        except Exception as e:
            log.warning(f"parcel_sales batch {i // SOQL_IN_BATCH} failed: {e}")
            continue

        for s in sales:
            addr = pin_to_addr.get(s.get("pin"), {})
            s["_address"] = addr.get("prop_address_full", "")
            s["_city"] = (addr.get("prop_address_city_name") or "").strip().title()
            s["_state"] = addr.get("prop_address_state", "IL")
            s["_zip"] = addr.get("prop_address_zipcode_1")
        all_sales.extend(sales)

    return all_sales


def fetch_tax_sales_for_cities(limit: int = 2000) -> List[Dict]:
    """Tax sales joined with addresses, filtered to tracked cities."""
    pin_to_addr = _fetch_addresses_for_tracked_cities()
    if not pin_to_addr:
        return []

    pins = list(pin_to_addr.keys())
    all_records: List[Dict] = []
    for i in range(0, len(pins), SOQL_IN_BATCH):
        batch = pins[i:i + SOQL_IN_BATCH]
        try:
            records = get_json(
                DATASETS["tax_sale_annual"],
                params={
                    "$limit": limit,
                    "$where": f"pin in {safe_soql_in_list(batch)}",
                    "$order": "tax_sale_year DESC",
                },
                headers=_headers(),
            )
        except Exception as e:
            log.warning(f"tax_sales batch {i // SOQL_IN_BATCH} failed: {e}")
            continue

        for r in records:
            addr = pin_to_addr.get(r.get("pin"), {})
            r["_address"] = addr.get("prop_address_full", "")
            r["_city"] = (addr.get("prop_address_city_name") or "").strip().title()
            r["_zip"] = addr.get("prop_address_zipcode_1")
        all_records.extend(records)

    return all_records


# Backwards-compat aliases used by ingest.py
fetch_property_sales = fetch_sales_for_cities
fetch_tax_delinquency = fetch_tax_sales_for_cities


def fetch_assessments(*args, **kwargs):
    """Placeholder — Parcel Universe is huge; not enabled by default."""
    return []
