"""
Orchestrates data ingestion into the database.

Per-record SAVEPOINT pattern: each row is wrapped in a `db.begin_nested()`
so that if one record fails (constraint violation, malformed data, etc.)
the rest of the batch still commits. Failed records are logged but don't
poison the whole run.
"""
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.property import Property
from app.models.sale import Sale
from app.models.foreclosure import Foreclosure, ForeclosureStatus
from app.models.bank_seizure import BankSeizure, SeizureType
from app.scrapers.chicago_data_portal import fetch_sales_for_cities, fetch_tax_sales_for_cities
from app.scrapers.cook_county_foreclosures import fetch_foreclosure_filings, normalize_foreclosure
from app.utils.normalize import normalize_address, normalize_city, normalize_pin, to_decimal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def _get_or_create_property(
    db: Session,
    address: str,
    city: str,
    zip_code: Optional[str] = None,
    pin: Optional[str] = None,
) -> Optional[Property]:
    address_norm = normalize_address(address)
    city_norm = normalize_city(city)
    pin_norm = normalize_pin(pin)

    if not address_norm or not city_norm:
        return None

    # Prefer PIN lookup when available
    if pin_norm:
        existing = db.query(Property).filter(Property.pin == pin_norm).first()
        if existing:
            return existing

    # Fall back to (address_normalized, city) — the dedup key index
    existing = (
        db.query(Property)
        .filter(Property.address_normalized == address_norm, Property.city == city_norm)
        .first()
    )
    if existing:
        # Backfill PIN if we now have one
        if pin_norm and not existing.pin:
            existing.pin = pin_norm
        return existing

    prop = Property(
        pin=pin_norm,
        address=address.strip(),
        address_normalized=address_norm,
        city=city_norm,
        state="IL",
        zip_code=zip_code,
        municipality=city_norm,
    )
    db.add(prop)
    db.flush()
    return prop


def _per_record(db: Session, fn, *args, **kwargs):
    """Run `fn` inside a SAVEPOINT. Returns True on success, False on failure."""
    try:
        with db.begin_nested():
            fn(*args, **kwargs)
        return True
    except IntegrityError as e:
        log.debug(f"Skipped duplicate: {e.orig}")
        return False
    except Exception as e:
        log.warning(f"Record failed: {e}")
        return False


def _ingest_sale_row(db: Session, raw: dict) -> None:
    address = (raw.get("_address") or "").strip()
    city = (raw.get("_city") or "").strip()
    pin = raw.get("pin")

    prop = _get_or_create_property(db, address=address, city=city, zip_code=raw.get("_zip"), pin=pin)
    if not prop:
        return

    sale_date_str = raw.get("sale_date", "")[:10] if raw.get("sale_date") else None
    sale_price = to_decimal(raw.get("sale_price"))
    if not sale_date_str or sale_price is None:
        return

    # Dedup via (property_id, sale_date, sale_price) — Decimal compare is exact.
    existing = db.query(Sale).filter(
        Sale.property_id == prop.id,
        Sale.sale_date == sale_date_str,
        Sale.sale_price == sale_price,
    ).first()
    if existing:
        return

    deed_type = raw.get("mydec_deed_type") or raw.get("deed_type")
    db.add(Sale(
        property_id=prop.id,
        sale_date=sale_date_str,
        sale_price=sale_price,
        seller_name=raw.get("seller_name"),
        buyer_name=raw.get("buyer_name"),
        deed_type=deed_type,
        document_number=raw.get("doc_no"),
        source="Cook County Assessor",
    ))


def ingest_sales(db: Session) -> int:
    log.info("Ingesting property sales from Cook County Assessor...")
    try:
        records = fetch_sales_for_cities(limit_per_city=500)
    except Exception as e:
        log.warning(f"Property sales dataset unreachable: {e}. Skipping.")
        return 0

    success = sum(1 for r in records if _per_record(db, _ingest_sale_row, r))
    db.commit()
    log.info(f"Ingested {success} new sale records (of {len(records)} candidates).")
    return success


def _ingest_foreclosure_row(db: Session, raw: dict) -> None:
    normalized = normalize_foreclosure(raw)
    address = normalized.get("address", "").strip()
    city = normalized.get("city", "").strip()
    if not address or not city:
        return

    prop = _get_or_create_property(db, address=address, city=city, zip_code=normalized.get("zip_code"))
    if not prop:
        return

    case_number = normalized.get("case_number")
    # Dedup on (property_id, case_number)
    if case_number:
        existing = db.query(Foreclosure).filter(
            Foreclosure.property_id == prop.id,
            Foreclosure.case_number == case_number,
        ).first()
        if existing:
            existing.status = ForeclosureStatus(normalized["status"])
            existing.updated_at = datetime.utcnow()
            return

    db.add(Foreclosure(
        property_id=prop.id,
        status=ForeclosureStatus(normalized["status"]),
        filing_date=normalized.get("filing_date"),
        plaintiff=normalized.get("plaintiff"),
        defendant=normalized.get("defendant"),
        case_number=case_number,
        original_loan_amount=to_decimal(normalized.get("original_loan_amount")),
        judgment_amount=to_decimal(normalized.get("judgment_amount")),
        source="Cook County Circuit Court",
    ))


def ingest_foreclosures(db: Session) -> int:
    log.info("Ingesting foreclosure filings...")
    try:
        raw_records = fetch_foreclosure_filings(
            date_from=date.today() - timedelta(days=180),
            limit=2000,
        )
    except Exception as e:
        log.warning(f"Foreclosure source unreachable: {e}. Skipping.")
        return 0

    if not raw_records:
        log.info("No current foreclosure feed available. Skipping.")
        return 0

    success = sum(1 for r in raw_records if _per_record(db, _ingest_foreclosure_row, r))
    db.commit()
    log.info(f"Ingested {success} new foreclosure records.")
    return success


def _ingest_tax_sale_row(db: Session, raw: dict) -> None:
    address = (raw.get("_address") or "").strip()
    city = (raw.get("_city") or "").strip()
    pin = raw.get("pin")

    prop = _get_or_create_property(db, address=address, city=city, zip_code=raw.get("_zip"), pin=pin)
    if not prop:
        return

    tax_year = raw.get("tax_sale_year")
    case_marker = str(tax_year) if tax_year else None

    existing = db.query(BankSeizure).filter(
        BankSeizure.property_id == prop.id,
        BankSeizure.seizure_type == SeizureType.tax_sale,
        BankSeizure.case_number == case_marker,
    ).first()
    if existing:
        return

    tax_amount = to_decimal(raw.get("total_tax_and_penalty_amount_offered"))

    db.add(BankSeizure(
        property_id=prop.id,
        seizure_type=SeizureType.tax_sale,
        seizure_date=f"{tax_year}-01-01" if tax_year else None,
        seizing_entity="Cook County Treasurer",
        seizing_entity_type="county",
        tax_delinquency_amount=tax_amount,
        lien_amount=tax_amount,
        case_number=case_marker,
        is_active=(str(raw.get("sold_at_sale", "")).upper() == "TRUE"),
        source="Cook County Treasurer",
    ))


def ingest_tax_sales(db: Session) -> int:
    log.info("Ingesting tax sale records from Cook County Treasurer...")
    try:
        records = fetch_tax_sales_for_cities(limit=2000)
    except Exception as e:
        log.warning(f"Tax sale dataset unreachable: {e}. Skipping.")
        return 0

    success = sum(1 for r in records if _per_record(db, _ingest_tax_sale_row, r))
    db.commit()
    log.info(f"Ingested {success} new tax-sale records.")
    return success


def run_full_ingest():
    db = SessionLocal()
    try:
        log.info("=== Full ingest started ===")
        ingest_sales(db)
        ingest_foreclosures(db)
        ingest_tax_sales(db)
        log.info("=== Full ingest complete ===")
    finally:
        db.close()


if __name__ == "__main__":
    run_full_ingest()
