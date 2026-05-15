"""
Market metrics endpoints.

GET /market-metrics                 — combined summary (FRED latest + computed)
GET /market-metrics/fred-series     — list of available FRED series with names
GET /market-metrics/fred/{series_id} — full time series for charting
POST /market-metrics/refresh-fred   — admin trigger to pull fresh FRED data
"""
import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.market_metric import MarketMetric
from app.scrapers.fred import SERIES, run_fred_ingest, FREDNotConfigured
from app.scrapers.chicago_distress import run_chicago_distress_ingest
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
