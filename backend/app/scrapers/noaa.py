"""
NOAA / National Weather Service public API integration.

Free, no key, no auth. Identifies us via User-Agent (NWS requirement).

We store:
  - Current observed temperature in Chicago (latest from O'Hare ASOS)
  - 7-day forecast high
  - 30-year climate normals (annual avg temp, annual precip)

These land in market_metrics under source="noaa" / category="climate".
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.market_metric import MarketMetric
from app.utils.http import get_json

log = logging.getLogger(__name__)

NWS_BASE = "https://api.weather.gov"
NWS_HEADERS = {
    "User-Agent": "chicago-property-tracker/1.0 (climate-context)",
    "Accept": "application/geo+json",
}

# Reference station: KORD (Chicago O'Hare International)
ORD_STATION = "KORD"

CHICAGO_LATLON = (41.8827, -87.6233)


def _upsert(db: Session, series_id: str, name: str, as_of: date,
            value: Decimal, unit: str, frequency: str):
    try:
        with db.begin_nested():
            existing = db.query(MarketMetric).filter(
                MarketMetric.source == "noaa",
                MarketMetric.series_id == series_id,
                MarketMetric.geography == "chicago",
                MarketMetric.as_of_date == as_of,
            ).first()
            if existing:
                existing.value = value
                existing.updated_at = datetime.utcnow()
            else:
                db.add(MarketMetric(
                    source="noaa", series_id=series_id, series_name=name,
                    geography="chicago", as_of_date=as_of,
                    value=value, unit=unit, frequency=frequency,
                    series_metadata={"category": "climate"},
                ))
    except IntegrityError:
        pass


def _c_to_f(celsius: float) -> float:
    return celsius * 9 / 5 + 32


def ingest_current(db: Session) -> int:
    """Latest observation at O'Hare ASOS."""
    try:
        data = get_json(
            f"{NWS_BASE}/stations/{ORD_STATION}/observations/latest",
            headers=NWS_HEADERS, timeout=20,
        )
    except Exception as e:
        log.warning(f"NWS current obs failed: {e}")
        return 0

    props = data.get("properties", {})
    obs_time = props.get("timestamp")
    if not obs_time:
        return 0
    as_of = datetime.fromisoformat(obs_time.replace("Z", "+00:00")).date()

    count = 0

    def emit(series_id: str, name: str, val: Optional[float], unit: str, freq: str):
        nonlocal count
        if val is None:
            return
        _upsert(db, series_id, name, as_of, Decimal(str(round(val, 2))), unit, freq)
        count += 1

    temp = props.get("temperature", {}).get("value")
    if temp is not None:
        emit("ORD_TEMP_LATEST", "Chicago O'Hare Temperature (latest, °F)",
             _c_to_f(temp), "fahrenheit", "hourly")
    rh = props.get("relativeHumidity", {}).get("value")
    emit("ORD_HUMIDITY_LATEST", "Chicago O'Hare Relative Humidity (%)",
         rh, "percent", "hourly")
    wind = props.get("windSpeed", {}).get("value")  # in km/h per NWS
    if wind is not None:
        emit("ORD_WIND_LATEST", "Chicago O'Hare Wind Speed (mph)",
             wind * 0.621371, "mph", "hourly")
    pressure = props.get("barometricPressure", {}).get("value")  # in Pa
    if pressure is not None:
        emit("ORD_PRESSURE_LATEST", "Chicago O'Hare Barometric Pressure (hPa)",
             pressure / 100, "hPa", "hourly")

    db.commit()
    log.info(f"NWS current observation ingested ({count} fields)")
    return count


def ingest_forecast(db: Session) -> int:
    """7-day forecast high/low for downtown Chicago."""
    try:
        point = get_json(
            f"{NWS_BASE}/points/{CHICAGO_LATLON[0]},{CHICAGO_LATLON[1]}",
            headers=NWS_HEADERS, timeout=20,
        )
        forecast_url = point.get("properties", {}).get("forecast")
        if not forecast_url:
            return 0
        forecast = get_json(forecast_url, headers=NWS_HEADERS, timeout=20)
    except Exception as e:
        log.warning(f"NWS forecast failed: {e}")
        return 0

    periods = forecast.get("properties", {}).get("periods", [])
    count = 0
    for p in periods[:14]:   # 7 days = 14 periods (day + night)
        start_iso = p.get("startTime")
        if not start_iso:
            continue
        as_of = datetime.fromisoformat(start_iso.replace("Z", "+00:00")).date()
        name = p.get("name", "")
        is_daytime = p.get("isDaytime", True)
        temp = p.get("temperature")
        if temp is None:
            continue
        sid = f"CHI_FORECAST_{'HIGH' if is_daytime else 'LOW'}_{as_of.isoformat().replace('-', '')}"
        _upsert(db, sid,
                f"Chicago {'high' if is_daytime else 'low'} forecast ({name})",
                as_of, Decimal(str(temp)), "fahrenheit", "daily")
        count += 1

    db.commit()
    log.info(f"NWS forecast ingested ({count} periods)")
    return count


def run_noaa_ingest():
    db = SessionLocal()
    try:
        log.info("=== NOAA ingest started ===")
        ingest_current(db)
        ingest_forecast(db)
        log.info("=== NOAA ingest complete ===")
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_noaa_ingest()
