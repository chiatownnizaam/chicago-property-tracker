"""
FRED (Federal Reserve Economic Data) integration.

Pulls free, public time-series for macro mortgage/foreclosure indicators.
National data is the most reliable; some series are available at state level
but the mortgage-quality ones (delinquency, foreclosure rate) generally
aren't.

Series picked to map onto the user-requested metrics:

  Delinquency / Foreclosure indicators
    DRSFRMACBS    Delinquency Rate on Single-Family Residential Mortgages,
                  All Commercial Banks (quarterly, %)
    DRBLACBS      Delinquency Rate on All Loans, All Commercial Banks (quarterly, %)
    CORSFRMACBS   Charge-Off Rate on Single-Family Residential Mortgages,
                  All Commercial Banks (quarterly, %)

  Macro / Housing market context
    MORTGAGE30US  30-Year Fixed Rate Mortgage Average in the United States
                  (weekly, %)
    ETOTALUSQ176N E&E REO ratio proxy: total bank-owned real estate
                  (quarterly) — used as REO inventory proxy

Each observation lands in `market_metrics` table, keyed by
(source, series_id, geography, as_of_date) so re-runs are idempotent.
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import List, Dict, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.market_metric import MarketMetric
from app.utils.http import get_json
from app.utils.normalize import to_decimal

log = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred"

# Curated series — friendly name + unit + frequency hint.
# Add more by editing this dict; the scraper handles any FRED series id.
SERIES: Dict[str, Dict[str, str]] = {
    "DRSFRMACBS": {
        "name": "Delinquency Rate, Single-Family Residential Mortgages",
        "unit": "percent",
        "frequency": "quarterly",
        "metric_tag": "delinquency_rate",
    },
    "DRBLACBS": {
        "name": "Delinquency Rate, All Loans, Commercial Banks",
        "unit": "percent",
        "frequency": "quarterly",
        "metric_tag": "delinquency_rate_total",
    },
    "CORSFRMACBS": {
        "name": "Charge-Off Rate, Single-Family Residential Mortgages",
        "unit": "percent",
        "frequency": "quarterly",
        "metric_tag": "chargeoff_rate",
    },
    "MORTGAGE30US": {
        "name": "30-Year Fixed Rate Mortgage Average",
        "unit": "percent",
        "frequency": "weekly",
        "metric_tag": "mortgage_30y_rate",
    },
}


class FREDNotConfigured(RuntimeError):
    """Raised when FRED_API_KEY is missing from settings."""


def _ensure_key() -> str:
    if not settings.FRED_API_KEY:
        raise FREDNotConfigured(
            "FRED_API_KEY not set — sign up at https://fredaccount.stlouisfed.org/apikeys "
            "and add it to backend/.env"
        )
    return settings.FRED_API_KEY


def fetch_observations(series_id: str, observation_start: Optional[str] = "2000-01-01") -> List[Dict]:
    """Return list of {date, value} for a series, sorted ascending by date."""
    params = {
        "series_id": series_id,
        "api_key": _ensure_key(),
        "file_type": "json",
        "sort_order": "asc",
    }
    if observation_start:
        params["observation_start"] = observation_start

    data = get_json(f"{FRED_BASE}/series/observations", params=params)
    return data.get("observations", [])


def ingest_series(db: Session, series_id: str) -> int:
    cfg = SERIES.get(series_id, {})
    name = cfg.get("name", series_id)
    unit = cfg.get("unit", "percent")
    freq = cfg.get("frequency")

    try:
        observations = fetch_observations(series_id)
    except FREDNotConfigured as e:
        log.warning(str(e))
        return 0
    except Exception as e:
        log.warning(f"FRED fetch failed for {series_id}: {e}")
        return 0

    count = 0
    for obs in observations:
        date_str = obs.get("date")
        raw_value = obs.get("value")
        # FRED uses "." to indicate missing values
        if not date_str or raw_value in (None, ".", ""):
            continue
        try:
            value = Decimal(raw_value)
        except Exception:
            continue

        try:
            with db.begin_nested():
                existing = db.query(MarketMetric).filter(
                    MarketMetric.source == "fred",
                    MarketMetric.series_id == series_id,
                    MarketMetric.geography == "national",
                    MarketMetric.as_of_date == date_str,
                ).first()

                if existing:
                    if existing.value != value:
                        existing.value = value
                        existing.updated_at = datetime.utcnow()
                else:
                    db.add(MarketMetric(
                        source="fred",
                        series_id=series_id,
                        series_name=name,
                        geography="national",
                        as_of_date=date_str,
                        value=value,
                        unit=unit,
                        frequency=freq,
                        series_metadata={"fred_series_id": series_id},
                    ))
                    count += 1
        except IntegrityError:
            continue

    db.commit()
    log.info(f"FRED {series_id}: ingested {count} new observations")
    return count


def run_fred_ingest():
    db = SessionLocal()
    try:
        log.info("=== FRED ingest started ===")
        for sid in SERIES:
            ingest_series(db, sid)
        log.info("=== FRED ingest complete ===")
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_fred_ingest()
