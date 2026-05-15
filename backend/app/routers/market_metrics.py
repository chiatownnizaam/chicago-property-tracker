"""
Market metrics endpoints.

GET /market-metrics                 — combined summary (FRED latest + computed)
GET /market-metrics/fred-series     — list of available FRED series with names
GET /market-metrics/fred/{series_id} — full time series for charting
POST /market-metrics/refresh-fred   — admin trigger to pull fresh FRED data
"""
import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.market_metric import MarketMetric
from app.models.bank_financial import BankFinancial
from app.scrapers.fred import SERIES, run_fred_ingest, FREDNotConfigured
from app.scrapers.chicago_distress import run_chicago_distress_ingest
from app.scrapers.ffiec import run_ffiec_ingest
from app.scrapers.fema_flood import run_fema_enrichment
from app.scrapers.noaa import run_noaa_ingest
from app.scrapers.cook_county_assessor import run_assessor_enrichment
from app.services.market_metrics import compute_tracked_metrics

log = logging.getLogger(__name__)
router = APIRouter(prefix="/market-metrics", tags=["market_metrics"])


@router.get("/")
def get_market_metrics(db: Session = Depends(get_db)):
    """One-shot summary: latest FRED value per series + computed local metrics."""
    # Latest FRED observation per series
    fred_latest = []
    for series_id, cfg in SERIES.items():
        latest = (
            db.query(MarketMetric)
            .filter(MarketMetric.source == "fred", MarketMetric.series_id == series_id)
            .order_by(desc(MarketMetric.as_of_date))
            .first()
        )
        if latest:
            fred_latest.append({
                "series_id": series_id,
                "name": latest.series_name,
                "geography": latest.geography,
                "as_of": latest.as_of_date.isoformat(),
                "value": float(latest.value),
                "unit": latest.unit,
                "frequency": latest.frequency,
            })
        else:
            fred_latest.append({
                "series_id": series_id,
                "name": cfg.get("name", series_id),
                "geography": "national",
                "as_of": None,
                "value": None,
                "unit": cfg.get("unit"),
                "frequency": cfg.get("frequency"),
                "note": "Run /market-metrics/refresh-fred to populate.",
            })

    # Chicago Data Portal series — one row per metric (latest only)
    chicago_rows = (
        db.query(MarketMetric)
        .filter(MarketMetric.source == "chicago_portal")
        .order_by(desc(MarketMetric.as_of_date))
        .all()
    )
    seen_chi_series = set()
    chicago_latest = []
    for r in chicago_rows:
        if r.series_id in seen_chi_series:
            continue
        seen_chi_series.add(r.series_id)
        chicago_latest.append({
            "series_id": r.series_id,
            "name": r.series_name,
            "geography": r.geography,
            "as_of": r.as_of_date.isoformat(),
            "value": float(r.value),
            "unit": r.unit,
            "frequency": r.frequency,
            "category": (r.series_metadata or {}).get("category", "distress"),
        })

    # NOAA weather/climate series (latest per series)
    noaa_rows = (
        db.query(MarketMetric)
        .filter(MarketMetric.source == "noaa")
        .order_by(desc(MarketMetric.as_of_date))
        .all()
    )
    seen_noaa = set()
    noaa_latest = []
    for r in noaa_rows:
        if r.series_id in seen_noaa:
            continue
        seen_noaa.add(r.series_id)
        noaa_latest.append({
            "series_id": r.series_id,
            "name": r.series_name,
            "geography": r.geography,
            "as_of": r.as_of_date.isoformat(),
            "value": float(r.value),
            "unit": r.unit,
            "frequency": r.frequency,
            "category": "climate",
        })

    # FFIEC Call Report series — derived metrics aggregated from IL banks
    ffiec_rows = (
        db.query(MarketMetric)
        .filter(MarketMetric.source == "ffiec")
        .order_by(desc(MarketMetric.as_of_date))
        .all()
    )
    seen_ffiec = set()
    ffiec_latest = []
    for r in ffiec_rows:
        if r.series_id in seen_ffiec:
            continue
        seen_ffiec.add(r.series_id)
        ffiec_latest.append({
            "series_id": r.series_id,
            "name": r.series_name,
            "geography": r.geography,
            "as_of": r.as_of_date.isoformat(),
            "value": float(r.value),
            "unit": r.unit,
            "frequency": r.frequency,
            "category": "credit",
        })

    local = compute_tracked_metrics(db)

    return {
        "macro": {
            "source": "FRED (Federal Reserve Economic Data)",
            "series": fred_latest,
        },
        "chicago": {
            "source": "Chicago Data Portal",
            "note": "Chicago city only — Skokie, Lincolnwood, Evanston are separate municipalities not in this data.",
            "series": chicago_latest,
        },
        "ffiec": {
            "source": "FFIEC Call Reports (via FDIC BankFind API)",
            "note": "Quarterly aggregates across all FDIC-insured Illinois banks.",
            "series": ffiec_latest,
        },
        "noaa": {
            "source": "National Weather Service (NWS API)",
            "note": "Current observations + 7-day forecast for Chicago (KORD).",
            "series": noaa_latest,
        },
        "tracked": local,
    }


@router.get("/fred-series")
def list_fred_series():
    """Discovery: what series do we know about?"""
    return [
        {"series_id": sid, **cfg}
        for sid, cfg in SERIES.items()
    ]


@router.get("/fred/{series_id}")
def get_fred_series(series_id: str, db: Session = Depends(get_db)):
    """Full time-series for a single FRED series — used by charts."""
    rows = (
        db.query(MarketMetric)
        .filter(MarketMetric.source == "fred", MarketMetric.series_id == series_id)
        .order_by(MarketMetric.as_of_date)
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No data for series {series_id}. Run /market-metrics/refresh-fred."
        )
    return {
        "series_id": series_id,
        "name": rows[0].series_name,
        "unit": rows[0].unit,
        "frequency": rows[0].frequency,
        "observations": [
            {"date": r.as_of_date.isoformat(), "value": float(r.value)}
            for r in rows
        ],
    }


@router.post("/refresh-fred")
def refresh_fred(background_tasks: BackgroundTasks):
    """Kicks off a FRED ingest in the background and returns immediately."""
    try:
        from app.scrapers.fred import _ensure_key
        _ensure_key()
    except FREDNotConfigured as e:
        raise HTTPException(status_code=400, detail=str(e))
    background_tasks.add_task(run_fred_ingest)
    return {"status": "ingest_started", "series": list(SERIES.keys())}


@router.post("/refresh-chicago")
def refresh_chicago(background_tasks: BackgroundTasks):
    """Refresh Chicago Data Portal aggregates (permits, vacant buildings, crime)."""
    background_tasks.add_task(run_chicago_distress_ingest)
    return {"status": "ingest_started"}


@router.post("/refresh-ffiec")
def refresh_ffiec(background_tasks: BackgroundTasks):
    """Refresh FFIEC Call Report aggregates + per-bank Cook County drill-down."""
    background_tasks.add_task(run_ffiec_ingest)
    return {"status": "ingest_started"}


@router.post("/refresh-fema")
def refresh_fema(background_tasks: BackgroundTasks):
    """Re-enrich all properties with FEMA flood zones."""
    background_tasks.add_task(run_fema_enrichment)
    return {"status": "ingest_started"}


@router.post("/refresh-noaa")
def refresh_noaa(background_tasks: BackgroundTasks):
    """Refresh current weather + forecast from NWS."""
    background_tasks.add_task(run_noaa_ingest)
    return {"status": "ingest_started"}


@router.post("/refresh-assessor")
def refresh_assessor(background_tasks: BackgroundTasks):
    """Re-enrich all properties from the Cook County Assessor."""
    background_tasks.add_task(run_assessor_enrichment)
    return {"status": "ingest_started"}


@router.get("/cook-county-banks")
def cook_county_banks(db: Session = Depends(get_db)):
    """
    Per-bank latest-quarter snapshot for Cook County, IL banks.
    Sorted by OREO% descending so most-stressed banks float to the top.
    """
    # Latest as_of_date per bank
    latest_date_subq = (
        db.query(
            BankFinancial.fdic_id,
            func.max(BankFinancial.as_of_date).label("latest"),
        )
        .filter(BankFinancial.county == "Cook")
        .group_by(BankFinancial.fdic_id)
        .subquery()
    )
    rows = (
        db.query(BankFinancial)
        .join(latest_date_subq,
              (BankFinancial.fdic_id == latest_date_subq.c.fdic_id) &
              (BankFinancial.as_of_date == latest_date_subq.c.latest))
        .order_by(BankFinancial.oreo_pct_assets.desc().nullslast())
        .all()
    )
    return {
        "as_of": rows[0].as_of_date.isoformat() if rows else None,
        "banks": [
            {
                "fdic_id": r.fdic_id,
                "name": r.name,
                "city": r.city,
                "county": r.county,
                "state": r.state,
                "as_of_date": r.as_of_date.isoformat(),
                "total_assets_thousands": float(r.total_assets),
                "oreo_thousands": float(r.oreo),
                "oreo_pct_assets": float(r.oreo_pct_assets) if r.oreo_pct_assets else 0,
            }
            for r in rows
        ],
    }


@router.get("/cook-county-banks/{fdic_id}")
def cook_county_bank_history(fdic_id: str, db: Session = Depends(get_db)):
    """Quarterly history for a single bank."""
    rows = (
        db.query(BankFinancial)
        .filter(BankFinancial.fdic_id == fdic_id)
        .order_by(BankFinancial.as_of_date)
        .all()
    )
    if not rows:
        raise HTTPException(404, "Bank not found")
    return {
        "fdic_id": fdic_id,
        "name": rows[-1].name,
        "city": rows[-1].city,
        "history": [
            {
                "as_of": r.as_of_date.isoformat(),
                "total_assets_thousands": float(r.total_assets),
                "oreo_thousands": float(r.oreo),
                "oreo_pct_assets": float(r.oreo_pct_assets) if r.oreo_pct_assets else 0,
            }
            for r in rows
        ],
    }


@router.get("/series/{source}/{series_id}")
def get_series_history(source: str, series_id: str, db: Session = Depends(get_db)):
    """Generic time-series fetch — works for fred / chicago_portal / ffiec."""
    rows = (
        db.query(MarketMetric)
        .filter(MarketMetric.source == source, MarketMetric.series_id == series_id)
        .order_by(MarketMetric.as_of_date)
        .all()
    )
    if not rows:
        raise HTTPException(404, f"No data for {source}/{series_id}")
    return {
        "source": source,
        "series_id": series_id,
        "name": rows[0].series_name,
        "unit": rows[0].unit,
        "frequency": rows[0].frequency,
        "geography": rows[0].geography,
        "observations": [
            {"date": r.as_of_date.isoformat(), "value": float(r.value)}
            for r in rows
        ],
    }
