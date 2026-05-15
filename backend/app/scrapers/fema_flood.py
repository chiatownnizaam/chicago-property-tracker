"""
FEMA flood-zone enrichment via the National Flood Hazard Layer (NFHL).

For every property with lat/lon, queries FEMA's public ArcGIS REST API
and stores the flood zone designation. Free, no auth.

Zones in FEMA's NFHL:
  A, AE, AH, AO, A1-A30  High-risk flood areas (Special Flood Hazard Area)
  V, VE, V1-V30          Coastal high-risk
  X (shaded)             Moderate risk (0.2% annual chance)
  X (unshaded)           Minimal risk
  D                      Undetermined risk
  (none)                 Outside any mapped flood zone
"""
import logging
import time
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.property import Property
from app.utils.http import get_json

log = logging.getLogger(__name__)

FEMA_NFHL_QUERY = (
    "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
)


def fetch_flood_zone(latitude: float, longitude: float) -> Tuple[Optional[str], Optional[str]]:
    """Returns (zone, subtype) for a point. (None, None) if unmapped."""
    params = {
        "geometry": f"{longitude},{latitude}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "FLD_ZONE,ZONE_SUBTY",
        "returnGeometry": "false",
        "f": "json",
    }
    try:
        data = get_json(FEMA_NFHL_QUERY, params=params, timeout=30)
    except Exception as e:
        log.warning(f"FEMA fetch failed for {latitude},{longitude}: {e}")
        return None, None
    features = data.get("features", [])
    if not features:
        return None, None
    attrs = features[0].get("attributes", {})
    return attrs.get("FLD_ZONE"), attrs.get("ZONE_SUBTY")


def enrich_flood_zone(prop) -> bool:
    """
    Enrich a single Property in-place. Returns True if updated, False if
    skipped (already enriched, no lat/lon, or FEMA unreachable).

    Caller is responsible for committing the session. Failures are silent so
    a flaky FEMA call never blocks an ingest.
    """
    if prop.flood_zone:
        return False
    if prop.latitude is None or prop.longitude is None:
        return False
    try:
        zone, subtype = fetch_flood_zone(float(prop.latitude), float(prop.longitude))
    except Exception as e:
        log.debug(f"FEMA enrichment skipped for {prop.address}: {e}")
        return False
    prop.flood_zone = zone or "UNMAPPED"
    prop.flood_zone_subtype = subtype
    prop.flood_zone_updated_at = datetime.utcnow()
    return True


def enrich_properties(db: Session, force: bool = False) -> int:
    """Enrich every property with lat/lon. Set force=True to overwrite."""
    query = db.query(Property).filter(
        Property.latitude.isnot(None), Property.longitude.isnot(None),
    )
    if not force:
        query = query.filter(Property.flood_zone.is_(None))

    properties = query.all()
    log.info(f"Enriching {len(properties)} properties with FEMA flood zones...")
    count = 0

    for prop in properties:
        zone, subtype = fetch_flood_zone(float(prop.latitude), float(prop.longitude))
        prop.flood_zone = zone or "UNMAPPED"
        prop.flood_zone_subtype = subtype
        prop.flood_zone_updated_at = datetime.utcnow()
        count += 1
        if count % 5 == 0:
            db.commit()
            log.info(f"  {count}/{len(properties)} processed")
        time.sleep(0.4)   # be polite to FEMA

    db.commit()
    log.info(f"FEMA enrichment complete: {count} properties updated")
    return count


def run_fema_enrichment():
    db = SessionLocal()
    try:
        enrich_properties(db)
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_fema_enrichment()
