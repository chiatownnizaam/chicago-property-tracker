"""
FFIEC Call Report aggregator via FDIC BankFind API.

For every quarter, fetches all FDIC-insured Illinois banks and aggregates:
  - Sum of Other Real Estate Owned (ORE field) — in $thousands
  - Sum of Total Assets (ASSET field) — in $thousands
  - Derived: OREO as % of Total Assets

Results stored in market_metrics with source="ffiec".

Notes:
  - FDIC API: https://api.fdic.gov/banks
  - Field reference: https://banks.data.fdic.gov/docs/  (RC line items)
  - Quarter-end dates: 0331, 0630, 0930, 1231
  - Rate limit visible in headers; we throttle conservatively
"""
import logging
import time
from datetime import date, datetime
from decimal import Decimal
from typing import List, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.market_metric import MarketMetric
from app.utils.http import get_json

log = logging.getLogger(__name__)

FDIC_BASE = "https://api.fdic.gov/banks"

# How far back to ingest by default.
DEFAULT_START_YEAR = 2015

# State filter — we focus on Illinois since that's where our tracked
# municipalities are. Easy to extend by adding more states here.
STATES = ["ILLINOIS"]


def _quarter_ends(start_year: int, end_year: int) -> List[str]:
    """Return YYYYMMDD strings for every quarter end in the inclusive range."""
    quarters = []
    for y in range(start_year, end_year + 1):
        for md in ("0331", "0630", "0930", "1231"):
            quarters.append(f"{y}{md}")
    return quarters


def _fetch_state_quarter(state: str, repdte: str) -> Tuple[int, int, int]:
    """Returns (bank_count, total_assets_thousands, total_ore_thousands)."""
    params = {
        "filters": f'STNAME:"{state}" AND REPDTE:{repdte}',
        "fields": "ASSET,ORE",
        "limit": 10000,
    }
    data = get_json(f"{FDIC_BASE}/financials", params=params, timeout=60)
    rows = data.get("data", [])

    total_assets = 0
    total_ore = 0
    for r in rows:
        d = r.get("data", {})
        total_assets += d.get("ASSET") or 0
        total_ore += d.get("ORE") or 0
    return len(rows), total_assets, total_ore


def _upsert(
    db: Session,
    series_id: str,
    series_name: str,
    geography: str,
    as_of: date,
    value: Decimal,
    unit: str,
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
                    source="ffiec",
                    series_id=series_id,
                    series_name=series_name,
                    geography=geography,
                    as_of_date=as_of,
                    value=value,
                    unit=unit,
                    frequency="quarterly",
                    series_metadata={"category": "credit"},
                ))
    except IntegrityError:
        pass


def ingest_ffiec_state(db: Session, state: str, start_year: int = DEFAULT_START_YEAR) -> int:
    """Aggregate OREO + Total Assets per quarter for a given state."""
    today = date.today()
    end_year = today.year

    quarters = _quarter_ends(start_year, end_year)
    geo_key = state.lower()
    count = 0

    for q in quarters:
        as_of = date(int(q[0:4]), int(q[4:6]), int(q[6:8]))
        if as_of > today:
            continue

        try:
            banks, assets, ore = _fetch_state_quarter(state, q)
        except Exception as e:
            log.warning(f"FDIC fetch failed for {state} {q}: {e}")
            time.sleep(2)
            continue

        if banks == 0:
            continue

        # OREO as % of total assets (the user's headline metric)
        pct = (Decimal(ore) / Decimal(assets) * 100) if assets else Decimal("0")

        _upsert(db, series_id=f"FFIEC_{state}_OREO_PCT_ASSETS",
                series_name=f"OREO % of Total Assets — {state.title()} banks",
                geography=geo_key, as_of=as_of, value=pct.quantize(Decimal("0.0001")),
                unit="percent")

        _upsert(db, series_id=f"FFIEC_{state}_OREO_TOTAL",
                series_name=f"Total OREO — {state.title()} banks ($ thousands)",
                geography=geo_key, as_of=as_of, value=Decimal(ore),
                unit="usd_thousands")

        _upsert(db, series_id=f"FFIEC_{state}_TOTAL_ASSETS",
                series_name=f"Total Bank Assets — {state.title()} banks ($ thousands)",
                geography=geo_key, as_of=as_of, value=Decimal(assets),
                unit="usd_thousands")

        _upsert(db, series_id=f"FFIEC_{state}_BANK_COUNT",
                series_name=f"FDIC-Insured Bank Count — {state.title()}",
                geography=geo_key, as_of=as_of, value=Decimal(banks),
                unit="count")

        count += 1
        log.info(f"  {state} {as_of}: {banks} banks, OREO=${ore:,}k, "
                 f"Assets=${assets:,}k, OREO%={pct:.4f}%")

        # Be polite — FDIC rate limit headers show low ceilings
        time.sleep(0.5)

    db.commit()
    return count


def run_ffiec_ingest():
    db = SessionLocal()
    try:
        log.info("=== FFIEC Call Report ingest started ===")
        for state in STATES:
            n = ingest_ffiec_state(db, state)
            log.info(f"  {state}: {n} quarters processed")
        log.info("=== FFIEC ingest complete ===")
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_ffiec_ingest()
