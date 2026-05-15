"""
FFIEC Call Report aggregator via FDIC BankFind API.

Three workloads:
  1. State-level aggregates (Illinois + comparison states + national)
     → stored in market_metrics with source="ffiec"
  2. Per-bank Cook County drill-down
     → stored in bank_financials table
  3. Both share the same /banks/financials endpoint

Field reference: https://banks.data.fdic.gov/docs/  (RC line items)
"""
import logging
import time
from datetime import date, datetime
from decimal import Decimal
from typing import List, Tuple, Optional, Iterator

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.market_metric import MarketMetric
from app.models.bank_financial import BankFinancial
from app.utils.http import get_json

log = logging.getLogger(__name__)

FDIC_BASE = "https://api.fdic.gov/banks"
DEFAULT_START_YEAR = 2015

# Geographies to aggregate.
# `state_filter`=None means national (no state filter at all).
GEOGRAPHIES = [
    {"key": "national", "label": "National (US)", "state_filter": None},
    {"key": "illinois", "label": "Illinois", "state_filter": "ILLINOIS"},
    {"key": "wisconsin", "label": "Wisconsin", "state_filter": "WISCONSIN"},
    {"key": "indiana", "label": "Indiana", "state_filter": "INDIANA"},
]

# County to drill into for per-bank data. Title Case (institutions endpoint).
COOK_COUNTY_FILTER = {
    "state_title": "Illinois",
    "county_title": "Cook",
}


def _quarter_ends(start_year: int, end_year: int) -> List[str]:
    out = []
    for y in range(start_year, end_year + 1):
        for md in ("0331", "0630", "0930", "1231"):
            out.append(f"{y}{md}")
    return out


# ---- State / national aggregates ------------------------------------------

def _fetch_aggregate(state_filter: Optional[str], repdte: str) -> Tuple[int, int, int]:
    """Returns (bank_count, total_assets_thousands, total_ore_thousands)."""
    filters = f"REPDTE:{repdte}"
    if state_filter:
        filters = f'STNAME:"{state_filter}" AND {filters}'
    params = {"filters": filters, "fields": "ASSET,ORE", "limit": 10000}
    data = get_json(f"{FDIC_BASE}/financials", params=params, timeout=60)
    rows = data.get("data", [])
    total_assets = sum((r["data"].get("ASSET") or 0) for r in rows)
    total_ore = sum((r["data"].get("ORE") or 0) for r in rows)
    return len(rows), total_assets, total_ore


def _upsert_metric(
    db: Session, series_id: str, series_name: str, geography: str,
    as_of: date, value: Decimal, unit: str,
):
    try:
        with db.begin_nested():
            existing = db.query(MarketMetric).filter(
                MarketMetric.source == "ffiec",
                MarketMetric.series_id == series_id,
                MarketMetric.geography == geography,
                MarketMetric.as_of_date == as_of,
            ).first()
            if existing:
                if existing.value != value:
                    existing.value = value
                    existing.updated_at = datetime.utcnow()
            else:
                db.add(MarketMetric(
                    source="ffiec", series_id=series_id, series_name=series_name,
                    geography=geography, as_of_date=as_of, value=value,
                    unit=unit, frequency="quarterly",
                    series_metadata={"category": "credit"},
                ))
    except IntegrityError:
        pass


def ingest_aggregate(db: Session, geo: dict, start_year: int = DEFAULT_START_YEAR) -> int:
    geo_key = geo["key"]
    label = geo["label"]
    state_filter = geo["state_filter"]
    today = date.today()
    count = 0

    for q in _quarter_ends(start_year, today.year):
        as_of = date(int(q[0:4]), int(q[4:6]), int(q[6:8]))
        if as_of > today:
            continue

        try:
            banks, assets, ore = _fetch_aggregate(state_filter, q)
        except Exception as e:
            log.warning(f"FDIC fetch failed for {label} {q}: {e}")
            time.sleep(2)
            continue

        if banks == 0:
            continue

        pct = (Decimal(ore) / Decimal(assets) * 100) if assets else Decimal("0")
        prefix = f"FFIEC_{geo_key.upper()}"
        _upsert_metric(db, f"{prefix}_OREO_PCT_ASSETS",
                       f"OREO % of Total Assets — {label}", geo_key, as_of,
                       pct.quantize(Decimal("0.0001")), "percent")
        _upsert_metric(db, f"{prefix}_OREO_TOTAL",
                       f"Total OREO — {label} ($ thousands)", geo_key, as_of,
                       Decimal(ore), "usd_thousands")
        _upsert_metric(db, f"{prefix}_TOTAL_ASSETS",
                       f"Total Bank Assets — {label} ($ thousands)", geo_key, as_of,
                       Decimal(assets), "usd_thousands")
        _upsert_metric(db, f"{prefix}_BANK_COUNT",
                       f"FDIC-Insured Bank Count — {label}", geo_key, as_of,
                       Decimal(banks), "count")
        count += 1
        log.info(f"  {label} {as_of}: {banks} banks, OREO=${ore:,}k, "
                 f"Assets=${assets:,}k, OREO%={pct:.4f}%")
        time.sleep(0.5)

    db.commit()
    return count


# ---- Per-bank Cook County drill-down --------------------------------------

def _list_cook_county_certs() -> List[dict]:
    """Active Cook County, IL bank institutions. Returns FDIC IDs + metadata."""
    params = {
        "filters": (
            f'STNAME:"{COOK_COUNTY_FILTER["state_title"]}" AND '
            f'COUNTY:"{COOK_COUNTY_FILTER["county_title"]}" AND ACTIVE:1'
        ),
        "fields": "ID,NAME,CITY,COUNTY,STNAME",
        "limit": 1000,
    }
    data = get_json(f"{FDIC_BASE}/institutions", params=params, timeout=60)
    return [r["data"] for r in data.get("data", [])]


def _fetch_bank_quarter(fdic_id: str, repdte: str) -> Optional[dict]:
    """Fetch one bank's financials for one quarter. Returns dict or None."""
    params = {
        "filters": f"ID:{fdic_id} AND REPDTE:{repdte}",
        "fields": "ASSET,ORE,NAME,CITY,STNAME",
        "limit": 1,
    }
    try:
        data = get_json(f"{FDIC_BASE}/financials", params=params, timeout=60)
    except Exception as e:
        log.warning(f"Bank {fdic_id} fetch failed for {repdte}: {e}")
        return None
    rows = data.get("data", [])
    if not rows:
        return None
    return rows[0].get("data")


def _upsert_bank(db: Session, fdic_id: str, name: str, city: str, county: str,
                 state: str, as_of: date, assets: int, oreo: int):
    pct = None
    if assets and assets > 0:
        pct = (Decimal(oreo) / Decimal(assets) * 100).quantize(Decimal("0.000001"))

    try:
        with db.begin_nested():
            existing = db.query(BankFinancial).filter(
                BankFinancial.fdic_id == fdic_id,
                BankFinancial.as_of_date == as_of,
            ).first()
            if existing:
                existing.total_assets = Decimal(assets)
                existing.oreo = Decimal(oreo)
                existing.oreo_pct_assets = pct
                existing.updated_at = datetime.utcnow()
            else:
                db.add(BankFinancial(
                    fdic_id=fdic_id, name=name, city=city,
                    county=county, state=state,
                    as_of_date=as_of,
                    total_assets=Decimal(assets),
                    oreo=Decimal(oreo),
                    oreo_pct_assets=pct,
                ))
    except IntegrityError:
        pass


def ingest_cook_county_banks(db: Session, start_year: int = 2020) -> int:
    """Per-bank quarterly Call Report data for Cook County IL banks."""
    log.info("Listing Cook County, IL banks...")
    banks = _list_cook_county_certs()
    log.info(f"  Found {len(banks)} active Cook County banks")

    today = date.today()
    quarters = _quarter_ends(start_year, today.year)
    count = 0

    for bank in banks:
        fdic_id = str(bank.get("ID", ""))
        name = bank.get("NAME", "")
        city = bank.get("CITY", "")
        county = bank.get("COUNTY", "")
        state = bank.get("STNAME", "")
        if not fdic_id or not name:
            continue

        for q in quarters:
            as_of = date(int(q[0:4]), int(q[4:6]), int(q[6:8]))
            if as_of > today:
                continue
            row = _fetch_bank_quarter(fdic_id, q)
            time.sleep(0.3)
            if not row:
                continue
            assets = row.get("ASSET") or 0
            oreo = row.get("ORE") or 0
            if not assets:
                continue
            _upsert_bank(db, fdic_id, name, city, county, state, as_of, assets, oreo)
            count += 1

        db.commit()
        log.info(f"  Processed {name} ({fdic_id})")

    log.info(f"  Total bank-quarter records ingested: {count}")
    return count


# ---- Top-level entry point -----------------------------------------------

def run_ffiec_ingest():
    db = SessionLocal()
    try:
        log.info("=== FFIEC ingest started ===")
        for geo in GEOGRAPHIES:
            n = ingest_aggregate(db, geo)
            log.info(f"  {geo['label']}: {n} quarters processed")
        log.info("=== State aggregates complete ===")
        log.info("=== Starting Cook County per-bank drill-down ===")
        ingest_cook_county_banks(db)
        log.info("=== FFIEC ingest complete ===")
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_ffiec_ingest()
