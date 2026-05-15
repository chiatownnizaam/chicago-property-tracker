"""
Ingest active listings from Redfin and Realtor.com.

Uses per-record SAVEPOINTs so one bad listing can't tank the whole batch.
Price-drop detection compares Decimal values (no float drift), and a
minimum-drop threshold filters out noise from rounding.
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.property import Property
from app.models.listing import Listing, PriceHistory, ListingSource, ListingStatus
from app.scrapers.redfin import fetch_all_listings as fetch_redfin
from app.scrapers.realtor import fetch_all_listings as fetch_realtor
from app.utils.normalize import normalize_address, normalize_city, to_decimal, to_coord

log = logging.getLogger(__name__)

# Below this absolute change we ignore the update (treat as noise).
MIN_PRICE_DELTA = Decimal("1.00")


def _get_or_create_property(
    db: Session,
    address: str,
    city: str,
    zip_code: Optional[str],
    latitude: Optional[float],
    longitude: Optional[float],
    bedrooms: Optional[int],
    bathrooms,
    sqft,
    year_built: Optional[int],
    property_type: Optional[str],
) -> Optional[Property]:
    address_norm = normalize_address(address)
    city_norm = normalize_city(city)
    if not address_norm or not city_norm:
        return None

    existing = (
        db.query(Property)
        .filter(Property.address_normalized == address_norm, Property.city == city_norm)
        .first()
    )
    if existing:
        if not existing.latitude and latitude:
            existing.latitude = to_coord(latitude)
        if not existing.longitude and longitude:
            existing.longitude = to_coord(longitude)
        return existing

    prop = Property(
        address=address.strip(),
        address_normalized=address_norm,
        city=city_norm,
        state="IL",
        zip_code=zip_code,
        municipality=city_norm,
        latitude=to_coord(latitude),
        longitude=to_coord(longitude),
        bedrooms=bedrooms,
        bathrooms=to_decimal(bathrooms),
        square_footage=to_decimal(sqft),
        year_built=year_built,
        property_type=property_type,
    )
    db.add(prop)
    db.flush()
    return prop


def _map_status(raw_status: Optional[str]) -> ListingStatus:
    if not raw_status:
        return ListingStatus.active
    s = raw_status.lower()
    if "pending" in s:
        return ListingStatus.pending
    if "contingent" in s:
        return ListingStatus.contingent
    if "sold" in s:
        return ListingStatus.sold
    if "withdrawn" in s or "expired" in s:
        return ListingStatus.withdrawn
    if "off market" in s or "off-market" in s:
        return ListingStatus.off_market
    return ListingStatus.active


def _parse_source(raw_source: str) -> Optional[ListingSource]:
    try:
        return ListingSource(raw_source)
    except (ValueError, KeyError):
        log.debug(f"Unknown listing source: {raw_source}")
        return None


def upsert_listing(db: Session, raw: Dict) -> Optional[Listing]:
    if not raw.get("address") or not raw.get("city") or not raw.get("current_price"):
        return None

    source = _parse_source(raw.get("source", ""))
    if source is None:
        return None

    prop = _get_or_create_property(
        db,
        address=raw["address"],
        city=raw["city"],
        zip_code=raw.get("zip_code"),
        latitude=raw.get("latitude"),
        longitude=raw.get("longitude"),
        bedrooms=raw.get("beds"),
        bathrooms=raw.get("baths"),
        sqft=raw.get("sqft"),
        year_built=raw.get("year_built"),
        property_type=raw.get("property_type"),
    )
    if not prop:
        return None

    source_id = raw.get("source_listing_id") or f"{source.value}-{prop.id}"
    new_price = to_decimal(raw["current_price"])
    if new_price is None:
        return None

    listing = (
        db.query(Listing)
        .filter(Listing.source == source, Listing.source_listing_id == source_id)
        .first()
    )

    today = date.today()
    if listing is None:
        listing = Listing(
            property_id=prop.id,
            source=source,
            source_listing_id=source_id,
            url=raw.get("url"),
            status=_map_status(raw.get("status")),
            list_date=raw.get("list_date") or today,
            current_price=new_price,
            original_price=new_price,
            lowest_price=new_price,
            highest_price=new_price,
            days_on_market=raw.get("days_on_market"),
            price_per_sqft=to_decimal(raw.get("price_per_sqft")),
            photo_url=raw.get("photo_url"),
            mls_number=raw.get("mls_number"),
            is_active=True,
            last_scraped_at=datetime.utcnow(),
        )
        db.add(listing)
        db.flush()
        db.add(PriceHistory(
            listing_id=listing.id,
            change_date=today,
            price=new_price,
        ))
        return listing

    # Existing listing — refresh and check for price change
    previous_price = listing.current_price
    listing.last_scraped_at = datetime.utcnow()
    listing.status = _map_status(raw.get("status"))
    listing.url = raw.get("url") or listing.url
    listing.photo_url = raw.get("photo_url") or listing.photo_url
    listing.days_on_market = raw.get("days_on_market") or listing.days_on_market
    listing.is_active = listing.status in (
        ListingStatus.active, ListingStatus.pending, ListingStatus.contingent,
    )

    delta = new_price - previous_price
    if abs(delta) < MIN_PRICE_DELTA:
        return listing

    pct = (delta / previous_price * 100) if previous_price else Decimal("0")

    listing.current_price = new_price
    listing.last_price_change_date = today
    if listing.lowest_price is None or new_price < listing.lowest_price:
        listing.lowest_price = new_price
    if listing.highest_price is None or new_price > listing.highest_price:
        listing.highest_price = new_price

    if delta < 0:
        listing.price_drops_count = (listing.price_drops_count or 0) + 1
        listing.total_price_drop_amount = (listing.total_price_drop_amount or Decimal("0")) + abs(delta)
        if listing.original_price:
            listing.total_price_drop_pct = (
                (listing.original_price - new_price) / listing.original_price * 100
            ).quantize(Decimal("0.01"))

    db.add(PriceHistory(
        listing_id=listing.id,
        change_date=today,
        price=new_price,
        previous_price=previous_price,
        change_amount=delta.quantize(Decimal("0.01")),
        change_percent=pct.quantize(Decimal("0.01")),
    ))
    return listing


def _per_record(db: Session, raw: Dict) -> bool:
    try:
        with db.begin_nested():
            upsert_listing(db, raw)
        return True
    except IntegrityError as e:
        log.debug(f"Listing skipped (integrity): {e.orig}")
        return False
    except Exception as e:
        log.warning(f"Listing upsert failed: {e}")
        return False


def ingest_redfin(db: Session) -> int:
    log.info("Ingesting Redfin listings...")
    try:
        records = fetch_redfin()
    except Exception as e:
        log.warning(f"Redfin ingest failed: {e}. Skipping.")
        return 0
    success = sum(1 for r in records if _per_record(db, r))
    db.commit()
    log.info(f"Redfin: {success}/{len(records)} listings ingested.")
    return success


def ingest_realtor(db: Session) -> int:
    log.info("Ingesting Realtor.com listings...")
    try:
        records = fetch_realtor()
    except Exception as e:
        log.warning(f"Realtor ingest failed: {e}. Skipping.")
        return 0
    success = sum(1 for r in records if _per_record(db, r))
    db.commit()
    log.info(f"Realtor: {success}/{len(records)} listings ingested.")
    return success


def run_listings_ingest():
    db = SessionLocal()
    try:
        log.info("=== Listings ingest started ===")
        ingest_redfin(db)
        ingest_realtor(db)
        log.info("=== Listings ingest complete ===")
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_listings_ingest()
