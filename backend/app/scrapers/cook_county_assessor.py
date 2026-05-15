"""
Cook County Assessor parcel-level enrichment.

Two datasets feed this:
  pabr-t5kh — Parcel Universe (Current Year Only)
              class, lat/lon, neighborhood, zip, township, municipality,
              walkability score, school district, flood-risk metadata
  x54s-btds — Single and Multi-Family Improvement Characteristics
              year_built, building_sqft, num_bedrooms, num_full_baths,
              num_half_baths, land_sqft

We match on PIN. Properties without a PIN are skipped. Fills missing fields
on the Property row first, then stores the full record in `parcel_data`
(JSON) for future reference.
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.property import Property
from app.utils.http import get_json
from app.utils.normalize import safe_soql_in_list

log = logging.getLogger(__name__)

COOK_COUNTY_BASE = "https://datacatalog.cookcountyil.gov/resource"

PARCEL_UNIVERSE = f"{COOK_COUNTY_BASE}/pabr-t5kh.json"
IMPROVEMENT_CHARS = f"{COOK_COUNTY_BASE}/x54s-btds.json"

SOQL_IN_BATCH = 200   # PINs per query


def _headers() -> dict:
    h = {"Accept": "application/json"}
    if settings.CHICAGO_DATA_PORTAL_APP_TOKEN:
        h["X-App-Token"] = settings.CHICAGO_DATA_PORTAL_APP_TOKEN
    return h


def _fetch_pin_batch(url: str, pins: List[str], extra_select: Optional[str] = None) -> Dict[str, Dict]:
    """Return {pin: row} dict for a batch of PINs against a Socrata dataset."""
    if not pins:
        return {}
    params = {
        "$limit": len(pins) * 10,
        "$where": f"pin in {safe_soql_in_list(pins)}",
    }
    if extra_select:
        params["$select"] = extra_select
    try:
        rows = get_json(url, params=params, headers=_headers(), timeout=60)
    except Exception as e:
        log.warning(f"Assessor fetch failed: {e}")
        return {}
    out: Dict[str, Dict] = {}
    for r in rows:
        pin = r.get("pin")
        if pin:
            # If multiple rows for same PIN (e.g., multi-year improvements),
            # keep the most recent.
            existing = out.get(pin)
            if existing:
                if (r.get("year") or 0) > (existing.get("year") or 0):
                    out[pin] = r
            else:
                out[pin] = r
    return out


def _apply_parcel_universe(prop: Property, row: Dict) -> None:
    """Fill in fields from pabr-t5kh row. Only sets missing values."""
    if not prop.latitude and row.get("lat"):
        try:
            prop.latitude = Decimal(str(row["lat"]))
        except Exception:
            pass
    if not prop.longitude and row.get("lon"):
        try:
            prop.longitude = Decimal(str(row["lon"]))
        except Exception:
            pass
    if not prop.zip_code and row.get("zip_code"):
        prop.zip_code = str(row["zip_code"])[:10]
    if not prop.municipality and row.get("cook_municipality_name"):
        prop.municipality = row["cook_municipality_name"]
    if not prop.property_class and row.get("class"):
        prop.property_class = str(row["class"])
    if not prop.neighborhood and row.get("nbhd_code"):
        prop.neighborhood = f"NBHD {row['nbhd_code']}"

    # Walkability score (CMAP)
    if row.get("access_cmap_walk_total_score") is not None:
        try:
            prop.walk_score = Decimal(str(row["access_cmap_walk_total_score"]))
        except Exception:
            pass

    # School district
    if not prop.school_district and row.get("school_unified_district_name"):
        prop.school_district = row["school_unified_district_name"]

    # Stash the full envelope for the UI to surface useful extras
    envelope = prop.parcel_data or {}
    envelope.update({
        "township": row.get("township_name"),
        "school_district": row.get("school_unified_district_name"),
        "park_district": row.get("tax_park_district_name"),
        "library_district": row.get("tax_library_district_name"),
        "fire_protection_district": row.get("tax_fire_protection_district_name"),
        "tif_district": row.get("tax_tif_district_name"),
        "fema_sfha": row.get("env_flood_fema_sfha"),
        "first_street_flood_factor": row.get("env_flood_fs_factor"),
        "first_street_flood_direction": row.get("env_flood_fs_risk_direction"),
        "ohare_noise_contour": row.get("env_ohare_noise_contour_half_mile_buffer_bool"),
        "airport_noise_dnl": row.get("env_airport_noise_dnl"),
        "walk_nta_score": row.get("access_cmap_walk_nta_score"),
        "walk_total_score": row.get("access_cmap_walk_total_score"),
        "census_tract": row.get("census_tract_geoid"),
    })
    prop.parcel_data = envelope


def _apply_improvements(prop: Property, row: Dict) -> None:
    """Fill year_built, sqft, beds, baths from x54s-btds. Only sets missing."""
    if not prop.year_built and row.get("year_built"):
        try:
            prop.year_built = int(row["year_built"])
        except (TypeError, ValueError):
            pass
    if not prop.square_footage and row.get("building_sqft"):
        try:
            prop.square_footage = Decimal(str(row["building_sqft"]))
        except Exception:
            pass
    if not prop.bedrooms and row.get("num_bedrooms"):
        try:
            prop.bedrooms = int(row["num_bedrooms"])
        except (TypeError, ValueError):
            pass
    if not prop.bathrooms:
        full = int(row.get("num_full_baths") or 0)
        half = int(row.get("num_half_baths") or 0)
        if full or half:
            prop.bathrooms = Decimal(full) + (Decimal(half) * Decimal("0.5"))
    if not prop.lot_size and row.get("land_sqft"):
        try:
            prop.lot_size = Decimal(str(row["land_sqft"])) / Decimal("43560")  # → acres
        except Exception:
            pass


def enrich_property(prop: Property) -> bool:
    """
    Enrich a single property by PIN. Cheap one-off call, useful inline.
    Returns True if any field was updated.
    """
    if not prop.pin:
        return False
    if prop.parcel_enriched_at:
        return False

    pin = prop.pin
    parcel = _fetch_pin_batch(PARCEL_UNIVERSE, [pin]).get(pin)
    if parcel:
        _apply_parcel_universe(prop, parcel)
    chars = _fetch_pin_batch(IMPROVEMENT_CHARS, [pin]).get(pin)
    if chars:
        _apply_improvements(prop, chars)
    prop.parcel_enriched_at = datetime.utcnow()
    return bool(parcel or chars)


def enrich_all_properties(db: Session, force: bool = False) -> int:
    """Bulk-enrich every property with a PIN."""
    query = db.query(Property).filter(Property.pin.isnot(None))
    if not force:
        query = query.filter(Property.parcel_enriched_at.is_(None))
    properties = query.all()
    log.info(f"Enriching {len(properties)} properties from Cook County Assessor...")
    if not properties:
        return 0

    by_pin = {p.pin: p for p in properties}
    pins = list(by_pin.keys())
    count = 0

    for i in range(0, len(pins), SOQL_IN_BATCH):
        batch = pins[i:i + SOQL_IN_BATCH]
        log.info(f"  Batch {i // SOQL_IN_BATCH + 1}: {len(batch)} PINs")
        parcel_rows = _fetch_pin_batch(PARCEL_UNIVERSE, batch)
        improvement_rows = _fetch_pin_batch(IMPROVEMENT_CHARS, batch)
        for pin in batch:
            prop = by_pin[pin]
            updated = False
            if pin in parcel_rows:
                _apply_parcel_universe(prop, parcel_rows[pin])
                updated = True
            if pin in improvement_rows:
                _apply_improvements(prop, improvement_rows[pin])
                updated = True
            if updated:
                prop.parcel_enriched_at = datetime.utcnow()
                count += 1
        db.commit()

    log.info(f"Cook County Assessor enrichment complete: {count} of {len(properties)} matched")
    return count


def run_assessor_enrichment():
    db = SessionLocal()
    try:
        enrich_all_properties(db)
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_assessor_enrichment()
