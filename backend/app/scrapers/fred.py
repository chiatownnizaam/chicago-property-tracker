"""
FRED (Federal Reserve Economic Data) integration.

Pulls free, public time-series for macro mortgage/foreclosure/housing
indicators. National data is the most reliable; some series are available
at state/MSA level (Chicago MSA, Illinois state).

Each observation lands in `market_metrics` table, keyed by
(source, series_id, geography, as_of_date) so re-runs are idempotent.

To add a series: find its ID at https://fred.stlouisfed.org and append
to the SERIES dict below. The scraper handles any FRED series.
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

log = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred"

# Categories (for grouping in UI):
#   credit       — delinquency, charge-off, foreclosure-related rates
#   prices       — home price indices, median sale prices
#   inventory    — housing supply, active listings, months of inventory
#   rates        — mortgage rates, fed funds, treasury yields
#   economy      — broader economic indicators correlated with housing distress
#
# Geography:
#   national     — US-wide
#   illinois     — IL state-level
#   chicago_msa  — Chicago-Naperville-Elgin MSA
SERIES: Dict[str, Dict[str, str]] = {
    # ---- Credit / delinquency -------------------------------------------------
    "DRSFRMACBS": {
        "name": "Delinquency Rate, Single-Family Residential Mortgages",
        "unit": "percent", "frequency": "quarterly",
        "category": "credit", "geography": "national",
    },
    "DRBLACBS": {
        "name": "Delinquency Rate, All Loans",
        "unit": "percent", "frequency": "quarterly",
        "category": "credit", "geography": "national",
    },
    "CORSFRMACBS": {
        "name": "Charge-Off Rate, Single-Family Residential Mortgages",
        "unit": "percent", "frequency": "quarterly",
        "category": "credit", "geography": "national",
    },
    "NPTLTL": {
        "name": "Nonperforming Loans (90+ DPD + nonaccrual) to Total Loans",
        "unit": "percent", "frequency": "quarterly",
        "category": "credit", "geography": "national",
    },
    "DRSREACBS": {
        "name": "Delinquency Rate, All Loans Secured by Real Estate",
        "unit": "percent", "frequency": "quarterly",
        "category": "credit", "geography": "national",
    },
    "DRCRELEXFACBS": {
        "name": "Delinquency Rate, Commercial Real Estate Loans (ex. Farmland)",
        "unit": "percent", "frequency": "quarterly",
        "category": "credit", "geography": "national",
    },
    "TLAACBM027SBOG": {
        "name": "Total Assets, All Commercial Banks",
        "unit": "usd_billions", "frequency": "monthly",
        "category": "credit", "geography": "national",
    },

    # ---- Home prices ---------------------------------------------------------
    "CSUSHPISA": {
        "name": "Case-Shiller US National Home Price Index (SA)",
        "unit": "index", "frequency": "monthly",
        "category": "prices", "geography": "national",
    },
    "CHXRSA": {
        "name": "Case-Shiller Chicago Home Price Index (SA)",
        "unit": "index", "frequency": "monthly",
        "category": "prices", "geography": "chicago_msa",
    },
    "ATNHPIUS16974Q": {
        "name": "FHFA Chicago-Naperville-Elgin MSA Home Price Index",
        "unit": "index", "frequency": "quarterly",
        "category": "prices", "geography": "chicago_msa",
    },
    "ILSTHPI": {
        "name": "FHFA All-Transactions House Price Index for Illinois",
        "unit": "index", "frequency": "quarterly",
        "category": "prices", "geography": "illinois",
    },
    "MSPUS": {
        "name": "Median Sales Price of Houses Sold",
        "unit": "usd", "frequency": "quarterly",
        "category": "prices", "geography": "national",
    },

    # ---- Inventory / supply --------------------------------------------------
    "MSACSR": {
        "name": "Monthly Supply of New Houses (months of inventory)",
        "unit": "months", "frequency": "monthly",
        "category": "inventory", "geography": "national",
    },
    "HOSINVUSM495N": {
        "name": "Active Listing Count (US)",
        "unit": "count", "frequency": "monthly",
        "category": "inventory", "geography": "national",
    },
    "HOUST": {
        "name": "Housing Starts (Total, Privately-Owned)",
        "unit": "count", "frequency": "monthly",
        "category": "inventory", "geography": "national",
    },
    "PERMIT": {
        "name": "Building Permits (New Private Housing Units Authorized)",
        "unit": "count", "frequency": "monthly",
        "category": "inventory", "geography": "national",
    },
    "ILBP1FH": {
        "name": "Illinois Single-Family Building Permits",
        "unit": "count", "frequency": "monthly",
        "category": "inventory", "geography": "illinois",
    },
    "RHVRUSQ156N": {
        "name": "Rental Vacancy Rate (US)",
        "unit": "percent", "frequency": "quarterly",
        "category": "inventory", "geography": "national",
    },
    "RHORUSQ156N": {
        "name": "Homeownership Rate (US)",
        "unit": "percent", "frequency": "quarterly",
        "category": "inventory", "geography": "national",
    },
    # ---- Rates ---------------------------------------------------------------
    "MORTGAGE30US": {
        "name": "30-Year Fixed Rate Mortgage Average",
        "unit": "percent", "frequency": "weekly",
        "category": "rates", "geography": "national",
    },
    "MORTGAGE15US": {
        "name": "15-Year Fixed Rate Mortgage Average",
        "unit": "percent", "frequency": "weekly",
        "category": "rates", "geography": "national",
    },
    "FEDFUNDS": {
        "name": "Federal Funds Effective Rate",
        "unit": "percent", "frequency": "monthly",
        "category": "rates", "geography": "national",
    },
    "DGS10": {
        "name": "10-Year Treasury Constant Maturity Rate",
        "unit": "percent", "frequency": "daily",
        "category": "rates", "geography": "national",
    },
    "DGS2": {
        "name": "2-Year Treasury Constant Maturity Rate",
        "unit": "percent", "frequency": "daily",
        "category": "rates", "geography": "national",
    },
    "DGS5": {
        "name": "5-Year Treasury Constant Maturity Rate",
        "unit": "percent", "frequency": "daily",
        "category": "rates", "geography": "national",
    },
    "DGS30": {
        "name": "30-Year Treasury Constant Maturity Rate",
        "unit": "percent", "frequency": "daily",
        "category": "rates", "geography": "national",
    },

    # ---- Broader economy -----------------------------------------------------
    "UNRATE": {
        "name": "US Unemployment Rate",
        "unit": "percent", "frequency": "monthly",
        "category": "economy", "geography": "national",
    },
    "ILUR": {
        "name": "Illinois Unemployment Rate",
        "unit": "percent", "frequency": "monthly",
        "category": "economy", "geography": "illinois",
    },
    "CHIC917URN": {
        "name": "Chicago-Naperville-Elgin MSA Unemployment Rate",
        "unit": "percent", "frequency": "monthly",
        "category": "economy", "geography": "chicago_msa",
    },
    "MEHOINUSA672N": {
        "name": "Real Median Household Income (US)",
        "unit": "usd", "frequency": "annual",
        "category": "economy", "geography": "national",
    },
    "MEHOINUSILA672N": {
        "name": "Real Median Household Income (Illinois)",
        "unit": "usd", "frequency": "annual",
        "category": "economy", "geography": "illinois",
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
    geography = cfg.get("geography", "national")

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
                    MarketMetric.geography == geography,
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
                        geography=geography,
                        as_of_date=date_str,
                        value=value,
                        unit=unit,
                        frequency=freq,
                        series_metadata={
                            "fred_series_id": series_id,
                            "category": cfg.get("category"),
                        },
                    ))
                    count += 1
        except IntegrityError:
            continue

    db.commit()
    log.info(f"FRED {series_id}: ingested {count} new observations ({geography})")
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
