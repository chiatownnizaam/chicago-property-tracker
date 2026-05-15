"""
Chicago Data Portal scrapers for city-level distress / activity signals.

Datasets (Socrata IDs verified live):
  ydr8-5enu — Building Permits
  7nii-7srd — 311 Service Requests: Vacant and Abandoned Buildings Reported (Historical)
  kc9i-wq85 — Vacant and Abandoned Buildings - Violations
  ijzp-q8t2 — Crimes - 2001 to Present  (≈8M rows, paginate carefully)

Results land in `market_metrics` with source="chicago_portal" and
geography="chicago" (these datasets cover Chicago proper only — Skokie,
Lincolnwood, Evanston are separate municipalities not in this data).
"""
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.market_metric import MarketMetric
from app.utils.http import get_json

log = logging.getLogger(__name__)

CITY_BASE = "https://data.cityofchicago.org/resource"

DATASETS = {
    "building_permits": f"{CITY_BASE}/ydr8-5enu.json",
    "vacant_buildings_311": f"{CITY_BASE}/7nii-7srd.json",
    "vacant_violations": f"{CITY_BASE}/kc9i-wq85.json",
    "crimes": f"{CITY_BASE}/ijzp-q8t2.json",
}


def _headers() -> dict:
    h = {"Accept": "application/json", "User-Agent": "chicago-property-tracker/1.0"}
    if settings.CHICAGO_DATA_PORTAL_APP_TOKEN:
        h["X-App-Token"] = settings.CHICAGO_DATA_PORTAL_APP_TOKEN
    return h


def _upsert_metric(
    db: Session,
    series_id: str,
    series_name: str,
    as_of_date: date,
    value: Decimal,
    unit: str,
    frequency: str,
    category: str,
    geography: str = "chicago",
) -> None:
    try:
        with db.begin_nested():
            existing = db.query(MarketMetric).filter(
                MarketMetric.source == "chicago_portal",
                MarketMetric.series_id == series_id,
                MarketMetric.geography == geography,
                MarketMetric.as_of_date == as_of_date,
            ).first()
            if existing:
                existing.value = value
                existing.updated_at = datetime.utcnow()
            else:
                db.add(MarketMetric(
                    source="chicago_portal",
                    series_id=series_id,
                    series_name=series_name,
                    geography=geography,
                    as_of_date=as_of_date,
                    value=value,
                    unit=unit,
                    frequency=frequency,
                    series_metadata={"category": category},
                ))
    except IntegrityError:
        pass


# ---- Counts via Socrata $select=count(*) ---------------------------------

def _count(url: str, where: str = None) -> int:
    params = {"$select": "count(*) as n"}
    if where:
        params["$where"] = where
    try:
        rows = get_json(url, params=params, headers=_headers(), timeout=60)
    except Exception as e:
        log.warning(f"count query failed for {url}: {e}")
        return 0
    if not rows:
        return 0
    try:
        return int(rows[0].get("n", 0))
    except (TypeError, ValueError):
        return 0


# ---- Public ingest entry points -----------------------------------------

def ingest_building_permits(db: Session) -> Dict[str, int]:
    """Permits issued in last 30 / 90 / 365 days (Chicago city only)."""
    log.info("Ingesting Chicago building permit counts...")
    today = date.today()
    out: Dict[str, int] = {}

    for days, label in [(30, "30d"), (90, "90d"), (365, "365d")]:
        cutoff = (today - timedelta(days=days)).isoformat()
        n = _count(
            DATASETS["building_permits"],
            where=f"issue_date >= '{cutoff}'",
        )
        _upsert_metric(
            db, series_id=f"chi_permits_{label}",
            series_name=f"Chicago Building Permits Issued ({label})",
            as_of_date=today, value=Decimal(n),
            unit="count", frequency="rolling",
            category="inventory",
        )
        out[label] = n
        log.info(f"  Building permits {label}: {n}")

    db.commit()
    return out


def ingest_vacant_buildings(db: Session) -> Dict[str, int]:
    """311 vacant/abandoned building reports + active violations (Chicago)."""
    log.info("Ingesting Chicago vacant-building counts...")
    today = date.today()
    out: Dict[str, int] = {}

    # 311 reports in last 365 days
    cutoff_365 = (today - timedelta(days=365)).isoformat()
    n_311 = _count(
        DATASETS["vacant_buildings_311"],
        where=f"date_service_request_was_received >= '{cutoff_365}'",
    )
    _upsert_metric(
        db, series_id="chi_vacant_311_365d",
        series_name="Chicago 311 Vacant/Abandoned Building Reports (365d)",
        as_of_date=today, value=Decimal(n_311),
        unit="count", frequency="rolling", category="distress",
    )
    out["vacant_311_365d"] = n_311
    log.info(f"  311 vacant building reports (365d): {n_311}")

    # Vacant building violations — total open
    n_violations = _count(DATASETS["vacant_violations"])
    _upsert_metric(
        db, series_id="chi_vacant_violations_total",
        series_name="Chicago Vacant Building Violations (total)",
        as_of_date=today, value=Decimal(n_violations),
        unit="count", frequency="point_in_time", category="distress",
    )
    out["vacant_violations_total"] = n_violations
    log.info(f"  Vacant building violations: {n_violations}")

    db.commit()
    return out


def ingest_crime_aggregates(db: Session) -> Dict[str, int]:
    """
    Aggregate crime counts for Chicago at city level.
    Totals + a handful of high-signal categories.
    """
    log.info("Ingesting Chicago crime aggregate counts...")
    today = date.today()
    out: Dict[str, int] = {}

    # Categories chosen for relevance to property buyers
    BUCKETS = {
        "all": None,
        "violent": "primary_type in ('HOMICIDE','ROBBERY','BATTERY','ASSAULT','CRIMINAL SEXUAL ASSAULT')",
        "property": "primary_type in ('THEFT','BURGLARY','MOTOR VEHICLE THEFT','CRIMINAL DAMAGE')",
        "narcotics": "primary_type = 'NARCOTICS'",
    }

    for days, label in [(30, "30d"), (365, "365d")]:
        cutoff = (today - timedelta(days=days)).isoformat()
        for bucket, where in BUCKETS.items():
            full_where = f"date >= '{cutoff}'"
            if where:
                full_where += f" AND {where}"
            n = _count(DATASETS["crimes"], where=full_where)
            sid = f"chi_crime_{bucket}_{label}"
            _upsert_metric(
                db, series_id=sid,
                series_name=f"Chicago Crimes - {bucket.title()} ({label})",
                as_of_date=today, value=Decimal(n),
                unit="count", frequency="rolling", category="safety",
            )
            out[sid] = n
            log.info(f"  {sid}: {n}")

    db.commit()
    return out


def run_chicago_distress_ingest():
    db = SessionLocal()
    try:
        log.info("=== Chicago distress ingest started ===")
        ingest_building_permits(db)
        ingest_vacant_buildings(db)
        ingest_crime_aggregates(db)
        log.info("=== Chicago distress ingest complete ===")
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_chicago_distress_ingest()
