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
from app.models.listing import Listing, ListingStatus


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

    # ---- REO lifecycle metrics (tracked sample) -----------------------------
    # Time-to-REO: avg days from foreclosure filing to REO seizure for the same
    # property. Only counts pairs where both records exist in our data.
    time_to_reo_pairs = (
        db.query(Foreclosure.filing_date, BankSeizure.seizure_date)
        .join(Property, Foreclosure.property_id == Property.id)
        .join(BankSeizure, BankSeizure.property_id == Property.id)
        .filter(tracked_property_filter)
        .filter(BankSeizure.seizure_type == SeizureType.reo)
        .filter(Foreclosure.filing_date.isnot(None))
        .filter(BankSeizure.seizure_date.isnot(None))
        .all()
    )
    time_to_reo_days_avg = None
    if time_to_reo_pairs:
        deltas = [(s - f).days for f, s in time_to_reo_pairs if s and f and s >= f]
        if deltas:
            time_to_reo_days_avg = round(sum(deltas) / len(deltas), 1)

    # Avg REO holding period: for closed REOs, release_date - seizure_date;
    # for currently-active REOs, today - seizure_date.
    reo_records = (
        db.query(BankSeizure.seizure_date, BankSeizure.release_date, BankSeizure.is_active)
        .join(Property, BankSeizure.property_id == Property.id)
        .filter(tracked_property_filter)
        .filter(BankSeizure.seizure_type == SeizureType.reo)
        .filter(BankSeizure.seizure_date.isnot(None))
        .all()
    )
    closed_days = []
    active_days = []
    for sd, rd, active in reo_records:
        if active:
            active_days.append((today - sd).days)
        elif rd:
            closed_days.append((rd - sd).days)

    avg_holding_period_closed = round(sum(closed_days) / len(closed_days), 1) if closed_days else None
    avg_age_active_reo = round(sum(active_days) / len(active_days), 1) if active_days else None

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

    # ---- Per-city breakdown (counts + listing metrics) -----------------------
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

        # Listings metrics — only active listings counted
        active_listings_q = (
            db.query(Listing)
            .join(Property, Listing.property_id == Property.id)
            .filter(Property.city == city)
            .filter(Listing.is_active.is_(True))
        )
        active_listings_count = active_listings_q.count()

        median_list_price = None
        avg_days_on_market = None
        listings_with_drops = 0
        pct_with_drops = 0.0
        if active_listings_count > 0:
            prices = sorted([float(l.current_price) for l in active_listings_q.all() if l.current_price])
            if prices:
                mid = len(prices) // 2
                median_list_price = (
                    prices[mid] if len(prices) % 2 == 1
                    else (prices[mid - 1] + prices[mid]) / 2
                )
            doms = [l.days_on_market for l in active_listings_q.all() if l.days_on_market]
            if doms:
                avg_days_on_market = round(sum(doms) / len(doms), 1)
            listings_with_drops = active_listings_q.filter(Listing.price_drops_count > 0).count()
            pct_with_drops = round(listings_with_drops / active_listings_count * 100, 1)

        by_city[city] = {
            "tracked_properties": int(city_props),
            "active_foreclosures": int(active),
            "reo_inventory": int(reo),
            "active_listings": int(active_listings_count),
            "median_list_price": median_list_price,
            "avg_days_on_market": avg_days_on_market,
            "listings_with_price_drops": int(listings_with_drops),
            "pct_listings_with_drops": pct_with_drops,
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
        "reo_lifecycle": {
            "time_to_reo_days_avg": time_to_reo_days_avg,
            "avg_holding_period_days_closed": avg_holding_period_closed,
            "avg_age_active_reo_days": avg_age_active_reo,
            "sample_size_time_to_reo": len(time_to_reo_pairs) if time_to_reo_pairs else 0,
            "sample_size_closed_reo": len(closed_days),
            "sample_size_active_reo": len(active_days),
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
