"""
Computed metrics from our local database.

These are honest counts and tracked-sample rates — they do NOT claim to
represent the true market-level foreclosure/delinquency picture for these
cities. That data isn't publicly available without paid feeds.

Returned shape is a list of metric dicts ready to be JSON-serialized.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.constants import TRACKED_CITIES
from app.models.property import Property
from app.models.foreclosure import Foreclosure, ForeclosureStatus
from app.models.bank_seizure import BankSeizure, SeizureType


# Statuses representing an actively-in-progress foreclosure (not dismissed,
# not yet exited via REO sale).
ACTIVE_FORECLOSURE_STATUSES = {
    ForeclosureStatus.lis_pendens,
    ForeclosureStatus.judgment,
    ForeclosureStatus.auction_scheduled,
}

# Statuses representing a completed foreclosure (loan exited the pipeline).
COMPLETED_FORECLOSURE_STATUSES = {
    ForeclosureStatus.sold_at_auction,
    ForeclosureStatus.reo,
}


def _rate_per_1000(numerator: int, denominator: int) -> Decimal:
    if not denominator:
        return Decimal("0")
    return (Decimal(numerator) / Decimal(denominator) * Decimal(1000)).quantize(Decimal("0.01"))


def compute_tracked_metrics(db: Session) -> Dict[str, object]:
    """Returns metrics + breakdowns scoped to the tracked municipalities."""
    today = date.today()
    last_30 = today - timedelta(days=30)
    last_90 = today - timedelta(days=90)
    last_365 = today - timedelta(days=365)

    tracked_property_filter = Property.city.in_(TRACKED_CITIES)
    total_properties = db.query(func.count(Property.id)).filter(tracked_property_filter).scalar() or 0

    # ---- Foreclosure counts -------------------------------------------------
    active_foreclosures = (
        db.query(func.count(Foreclosure.id))
        .join(Property, Foreclosure.property_id == Property.id)
        .filter(tracked_property_filter)
        .filter(Foreclosure.status.in_(list(ACTIVE_FORECLOSURE_STATUSES)))
        .scalar() or 0
    )

    foreclosure_starts_30d = (
        db.query(func.count(Foreclosure.id))
        .join(Property, Foreclosure.property_id == Property.id)
        .filter(tracked_property_filter)
        .filter(Foreclosure.filing_date >= last_30)
        .scalar() or 0
    )

    foreclosure_starts_365d = (
        db.query(func.count(Foreclosure.id))
        .join(Property, Foreclosure.property_id == Property.id)
        .filter(tracked_property_filter)
        .filter(Foreclosure.filing_date >= last_365)
        .scalar() or 0
    )

    completed_90d = (
        db.query(func.count(Foreclosure.id))
        .join(Property, Foreclosure.property_id == Property.id)
        .filter(tracked_property_filter)
        .filter(Foreclosure.status.in_(list(COMPLETED_FORECLOSURE_STATUSES)))
        .filter(Foreclosure.updated_at >= last_90)
        .scalar() or 0
    )

    total_completed = (
        db.query(func.count(Foreclosure.id))
        .join(Property, Foreclosure.property_id == Property.id)
        .filter(tracked_property_filter)
        .filter(Foreclosure.status.in_(list(COMPLETED_FORECLOSURE_STATUSES)))
        .scalar() or 0
    )

    total_foreclosures = (
        db.query(func.count(Foreclosure.id))
        .join(Property, Foreclosure.property_id == Property.id)
        .filter(tracked_property_filter)
        .scalar() or 0
    )

    # ---- REO inventory ------------------------------------------------------
    reo_inventory = (
        db.query(func.count(BankSeizure.id))
        .join(Property, BankSeizure.property_id == Property.id)
        .filter(tracked_property_filter)
        .filter(BankSeizure.seizure_type == SeizureType.reo)
        .filter(BankSeizure.is_active.is_(True))
        .scalar() or 0
    )

    reo_disposed_90d = (
        db.query(func.count(BankSeizure.id))
        .join(Property, BankSeizure.property_id == Property.id)
        .filter(tracked_property_filter)
        .filter(BankSeizure.seizure_type == SeizureType.reo)
        .filter(BankSeizure.is_active.is_(False))
        .filter(BankSeizure.release_date >= last_90)
        .scalar() or 0
    )

    # Tax delinquency = leading indicator we DO have
    tax_distress_active = (
        db.query(func.count(BankSeizure.id))
        .join(Property, BankSeizure.property_id == Property.id)
        .filter(tracked_property_filter)
        .filter(BankSeizure.seizure_type.in_([SeizureType.tax_lien, SeizureType.tax_sale]))
        .filter(BankSeizure.is_active.is_(True))
        .scalar() or 0
    )

    # ---- Derived rates (per 1,000 tracked properties — honest denominator) --
    foreclosure_rate_per_1000 = _rate_per_1000(active_foreclosures, total_properties)
    start_rate_30d_per_1000 = _rate_per_1000(foreclosure_starts_30d, total_properties)
    reo_per_1000 = _rate_per_1000(reo_inventory, total_properties)

    completion_rate_pct = (
        (Decimal(total_completed) / Decimal(total_foreclosures) * 100).quantize(Decimal("0.01"))
        if total_foreclosures else Decimal("0")
    )

    reo_disposition_pct = (
        (Decimal(reo_disposed_90d) / Decimal(reo_inventory + reo_disposed_90d) * 100).quantize(Decimal("0.01"))
        if (reo_inventory + reo_disposed_90d) > 0 else Decimal("0")
    )

    # ---- Per-city breakdown (counts) ----------------------------------------
    by_city = {}
    for city in TRACKED_CITIES:
        city_props = (
            db.query(func.count(Property.id))
            .filter(Property.city == city)
            .scalar() or 0
        )
        active = (
            db.query(func.count(Foreclosure.id))
            .join(Property, Foreclosure.property_id == Property.id)
            .filter(Property.city == city)
            .filter(Foreclosure.status.in_(list(ACTIVE_FORECLOSURE_STATUSES)))
            .scalar() or 0
        )
        reo = (
            db.query(func.count(BankSeizure.id))
            .join(Property, BankSeizure.property_id == Property.id)
            .filter(Property.city == city)
            .filter(BankSeizure.seizure_type == SeizureType.reo)
            .filter(BankSeizure.is_active.is_(True))
            .scalar() or 0
        )
        by_city[city] = {
            "tracked_properties": int(city_props),
            "active_foreclosures": int(active),
            "reo_inventory": int(reo),
        }

    return {
        "as_of": today.isoformat(),
        "denominator_caveat": (
            "Rates are computed against the count of tracked properties in our "
            "database, NOT against actual outstanding mortgages. Use macro tier "
            "for true market rates."
        ),
        "totals": {
            "tracked_properties": int(total_properties),
            "active_foreclosures": int(active_foreclosures),
            "foreclosure_starts_30d": int(foreclosure_starts_30d),
            "foreclosure_starts_365d": int(foreclosure_starts_365d),
            "foreclosures_completed_90d": int(completed_90d),
            "total_completed_foreclosures": int(total_completed),
            "total_foreclosure_filings": int(total_foreclosures),
            "reo_inventory": int(reo_inventory),
            "reo_disposed_90d": int(reo_disposed_90d),
            "active_tax_distress": int(tax_distress_active),
        },
        "rates": {
            "foreclosure_rate_per_1000_tracked": float(foreclosure_rate_per_1000),
            "foreclosure_start_rate_30d_per_1000_tracked": float(start_rate_30d_per_1000),
            "foreclosure_completion_rate_pct": float(completion_rate_pct),
            "reo_per_1000_tracked": float(reo_per_1000),
            "reo_disposition_rate_90d_pct": float(reo_disposition_pct),
        },
        "by_city": by_city,
    }
