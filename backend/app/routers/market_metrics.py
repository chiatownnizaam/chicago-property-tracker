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

    local = compute_tracked_metrics(db)

    return {
        "macro": {
            "source": "FRED (Federal Reserve Economic Data)",
            "series": fred_latest,
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
        # Light validation that the key is configured
        from app.scrapers.fred import _ensure_key
        _ensure_key()
    except FREDNotConfigured as e:
        raise HTTPException(status_code=400, detail=str(e))
    background_tasks.add_task(run_fred_ingest)
    return {"status": "ingest_started", "series": list(SERIES.keys())}
