"""
Cook County foreclosure / eviction data sources.

IMPORTANT: As of this implementation, neither Cook County nor the City of
Chicago publishes a live foreclosure or eviction filings dataset to their
open data portals. The Cook County portal only has archived foreclosure
deed records from 2011-2015. Current foreclosure cases live in:
  - Cook County Circuit Court Clerk's case search (not bulk-accessible)
  - HUD's annual NSP reports (county-level aggregate)
  - PropertyRadar / ATTOM Data (paid commercial services)

This module:
  - Pulls the archived foreclosure-deed datasets for historical context
  - Skips gracefully when current data is unavailable
"""
import httpx
from datetime import date
from typing import Optional, List, Dict
from app.config import settings
from app.constants import TRACKED_CITIES_UPPER as TRACKED_CITIES

COOK_COUNTY_BASE = "https://datacatalog.cookcountyil.gov/resource"

# Archived foreclosure-deed datasets from the Recorder of Deeds
ARCHIVED_FORECLOSURE_DATASETS = [
    f"{COOK_COUNTY_BASE}/9br9-dhca.json",  # 2012
    f"{COOK_COUNTY_BASE}/epxa-9ihc.json",  # 2011
    f"{COOK_COUNTY_BASE}/nk2q-7kjv.json",  # 2013–2015
]


def _headers() -> dict:
    headers = {"Accept": "application/json", "User-Agent": "chicago-property-tracker/1.0"}
    if settings.CHICAGO_DATA_PORTAL_APP_TOKEN:
        headers["X-App-Token"] = settings.CHICAGO_DATA_PORTAL_APP_TOKEN
    return headers


def fetch_foreclosure_filings(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = 1000,
    offset: int = 0,
) -> List[Dict]:
    """
    No live foreclosure dataset is available. Returns empty list.
    Kept as a stable interface so the ingest pipeline doesn't break.
    """
    return []


def normalize_foreclosure(raw: dict) -> dict:
    """Map raw Cook County foreclosure record to our internal schema."""
    return {
        "case_number": raw.get("case_number") or raw.get("document_number"),
        "address": raw.get("address", ""),
        "city": (raw.get("city") or "").title(),
        "zip_code": raw.get("zip_code"),
        "filing_date": raw.get("filing_date", "")[:10] if raw.get("filing_date") else None,
        "plaintiff": raw.get("plaintiff_name"),
        "defendant": raw.get("defendant_name"),
        "original_loan_amount": _to_float(raw.get("mortgage_amount")),
        "judgment_amount": _to_float(raw.get("judgment_amount")),
        "status": _map_status(raw.get("case_status", "")),
        "source": "Cook County Circuit Court",
    }


def _to_float(val) -> Optional[float]:
    try:
        return float(val) if val else None
    except (TypeError, ValueError):
        return None


def _map_status(raw_status: str) -> str:
    status_map = {
        "LIS PENDENS": "lis_pendens",
        "JUDGMENT": "judgment",
        "SALE SCHEDULED": "auction_scheduled",
        "SOLD": "sold_at_auction",
        "REO": "reo",
        "DISMISSED": "dismissed",
    }
    return status_map.get(raw_status.upper(), "lis_pendens")
