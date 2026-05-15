from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, select, case, exists
from typing import Optional
from app.database import get_db
from app.models.property import Property
from app.models.foreclosure import Foreclosure
from app.models.eviction import Eviction
from app.models.bank_seizure import BankSeizure
from app.models.sale import Sale
from app.schemas.property import PropertyCreate, PropertyRead, PropertySummary
from app.utils.normalize import normalize_address, normalize_pin, normalize_city
from app.constants import TRACKED_CITIES

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("/", response_model=list[PropertySummary])
def list_properties(
    city: Optional[str] = Query(None),
    zip_code: Optional[str] = Query(None),
    has_foreclosure: Optional[bool] = Query(None),
    has_eviction: Optional[bool] = Query(None),
    has_bank_seizure: Optional[bool] = Query(None),
    min_value: Optional[float] = Query(None),
    max_value: Optional[float] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    # Subquery: latest sale per property (single query, no N+1).
    latest_sale_subq = (
        select(
            Sale.property_id.label("property_id"),
            func.max(Sale.sale_date).label("latest_sale_date"),
        )
        .group_by(Sale.property_id)
        .subquery()
    )

    latest_sale = (
        select(Sale.property_id, Sale.sale_date, Sale.sale_price)
        .join(
            latest_sale_subq,
            (Sale.property_id == latest_sale_subq.c.property_id)
            & (Sale.sale_date == latest_sale_subq.c.latest_sale_date),
        )
        .subquery()
    )

    # Boolean flags expressed in-query so we never load relationship rows.
    has_foreclosure_expr = exists().where(Foreclosure.property_id == Property.id)
    has_eviction_expr = exists().where(Eviction.property_id == Property.id)
    has_seizure_expr = exists().where(BankSeizure.property_id == Property.id)

    stmt = (
        select(
            Property.id,
            Property.pin,
            Property.address,
            Property.city,
            Property.latitude,
            Property.longitude,
            Property.market_value,
            has_foreclosure_expr.label("has_foreclosure"),
            has_eviction_expr.label("has_eviction"),
            has_seizure_expr.label("has_bank_seizure"),
            latest_sale.c.sale_price.label("last_sale_price"),
            latest_sale.c.sale_date.label("last_sale_date"),
        )
        .outerjoin(latest_sale, latest_sale.c.property_id == Property.id)
        .where(Property.city.in_(TRACKED_CITIES))
    )

    if city:
        stmt = stmt.where(Property.city.ilike(f"%{city}%"))
    if zip_code:
        stmt = stmt.where(Property.zip_code == zip_code)
    if min_value is not None:
        stmt = stmt.where(Property.market_value >= min_value)
    if max_value is not None:
        stmt = stmt.where(Property.market_value <= max_value)
    if has_foreclosure:
        stmt = stmt.where(has_foreclosure_expr)
    if has_eviction:
        stmt = stmt.where(has_eviction_expr)
    if has_bank_seizure:
        stmt = stmt.where(has_seizure_expr)

    rows = db.execute(stmt.offset(offset).limit(limit)).all()

    return [
        PropertySummary(
            id=r.id,
            pin=r.pin,
            address=r.address,
            city=r.city,
            latitude=float(r.latitude) if r.latitude is not None else None,
            longitude=float(r.longitude) if r.longitude is not None else None,
            market_value=float(r.market_value) if r.market_value is not None else None,
            has_foreclosure=bool(r.has_foreclosure),
            has_eviction=bool(r.has_eviction),
            has_bank_seizure=bool(r.has_bank_seizure),
            last_sale_price=float(r.last_sale_price) if r.last_sale_price is not None else None,
            last_sale_date=str(r.last_sale_date) if r.last_sale_date else None,
        )
        for r in rows
    ]


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Single-query stats per tracked city using LEFT JOIN + GROUP BY."""
    # Build aggregate subqueries per event type — each scoped by property city.
    foreclosure_counts = (
        select(Property.city.label("city"), func.count(Foreclosure.id).label("n"))
        .join(Foreclosure, Foreclosure.property_id == Property.id)
        .where(Property.city.in_(TRACKED_CITIES))
        .group_by(Property.city)
        .subquery()
    )
    eviction_counts = (
        select(Property.city.label("city"), func.count(Eviction.id).label("n"))
        .join(Eviction, Eviction.property_id == Property.id)
        .where(Property.city.in_(TRACKED_CITIES))
        .group_by(Property.city)
        .subquery()
    )
    seizure_counts = (
        select(Property.city.label("city"), func.count(BankSeizure.id).label("n"))
        .join(BankSeizure, BankSeizure.property_id == Property.id)
        .where(Property.city.in_(TRACKED_CITIES))
        .group_by(Property.city)
        .subquery()
    )

    stmt = (
        select(
            Property.city,
            func.count(Property.id).label("total_properties"),
            func.avg(Property.market_value).label("avg_market_value"),
            func.coalesce(foreclosure_counts.c.n, 0).label("foreclosures"),
            func.coalesce(eviction_counts.c.n, 0).label("evictions"),
            func.coalesce(seizure_counts.c.n, 0).label("bank_seizures"),
        )
        .outerjoin(foreclosure_counts, foreclosure_counts.c.city == Property.city)
        .outerjoin(eviction_counts, eviction_counts.c.city == Property.city)
        .outerjoin(seizure_counts, seizure_counts.c.city == Property.city)
        .where(Property.city.in_(TRACKED_CITIES))
        .group_by(
            Property.city,
            foreclosure_counts.c.n,
            eviction_counts.c.n,
            seizure_counts.c.n,
        )
    )

    rows = db.execute(stmt).all()

    stats = {city: {"total_properties": 0, "foreclosures": 0, "evictions": 0,
                    "bank_seizures": 0, "avg_market_value": None} for city in TRACKED_CITIES}
    for r in rows:
        stats[r.city] = {
            "total_properties": int(r.total_properties or 0),
            "foreclosures": int(r.foreclosures or 0),
            "evictions": int(r.evictions or 0),
            "bank_seizures": int(r.bank_seizures or 0),
            "avg_market_value": round(float(r.avg_market_value), 2) if r.avg_market_value else None,
        }
    return stats


@router.get("/{property_id}", response_model=PropertyRead)
def get_property(property_id: int, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


@router.get("/{property_id}/history")
def get_property_history(property_id: int, db: Session = Depends(get_db)):
    """Unified timeline of every event for a property."""
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    timeline = []

    for s in prop.sales:
        timeline.append({
            "type": "sale",
            "date": s.sale_date.isoformat() if s.sale_date else None,
            "title": f"Sold for ${float(s.sale_price):,.0f}" if s.sale_price else "Sale",
            "amount": float(s.sale_price) if s.sale_price else None,
            "details": {
                "buyer": s.buyer_name,
                "seller": s.seller_name,
                "deed_type": s.deed_type,
                "document_number": s.document_number,
            },
        })

    for f in prop.foreclosures:
        timeline.append({
            "type": "foreclosure",
            "date": f.filing_date.isoformat() if f.filing_date else None,
            "title": f"Foreclosure: {f.status.value.replace('_', ' ')}",
            "amount": float(f.judgment_amount or f.original_loan_amount) if (f.judgment_amount or f.original_loan_amount) else None,
            "details": {
                "case_number": f.case_number,
                "plaintiff": f.plaintiff,
                "defendant": f.defendant,
                "judgment_amount": float(f.judgment_amount) if f.judgment_amount else None,
                "original_loan_amount": float(f.original_loan_amount) if f.original_loan_amount else None,
                "auction_date": f.auction_date.isoformat() if f.auction_date else None,
            },
        })

    for e in prop.evictions:
        timeline.append({
            "type": "eviction",
            "date": e.filing_date.isoformat() if e.filing_date else None,
            "title": f"Eviction: {e.status.value.replace('_', ' ')}",
            "amount": float(e.amount_owed) if e.amount_owed else None,
            "details": {
                "case_number": e.case_number,
                "plaintiff": e.plaintiff,
                "defendant": e.defendant,
                "reason": e.eviction_reason,
                "monthly_rent": float(e.monthly_rent) if e.monthly_rent else None,
            },
        })

    for b in prop.bank_seizures:
        timeline.append({
            "type": "bank_seizure",
            "date": b.seizure_date.isoformat() if b.seizure_date else None,
            "title": f"{b.seizure_type.value.replace('_', ' ').title()} by {b.seizing_entity or 'unknown'}",
            "amount": float(b.lien_amount or b.tax_delinquency_amount) if (b.lien_amount or b.tax_delinquency_amount) else None,
            "details": {
                "seizure_type": b.seizure_type.value,
                "seizing_entity": b.seizing_entity,
                "tax_delinquency_amount": float(b.tax_delinquency_amount) if b.tax_delinquency_amount else None,
                "lien_amount": float(b.lien_amount) if b.lien_amount else None,
                "is_active": b.is_active,
            },
        })

    listings_out = []
    for l in prop.listings:
        listings_out.append({
            "id": l.id,
            "source": l.source.value,
            "url": l.url,
            "status": l.status.value,
            "list_date": l.list_date.isoformat() if l.list_date else None,
            "current_price": float(l.current_price) if l.current_price else None,
            "original_price": float(l.original_price) if l.original_price else None,
            "lowest_price": float(l.lowest_price) if l.lowest_price else None,
            "price_drops_count": l.price_drops_count,
            "total_price_drop_amount": float(l.total_price_drop_amount or 0),
            "total_price_drop_pct": float(l.total_price_drop_pct or 0),
            "days_on_market": l.days_on_market,
            "photo_url": l.photo_url,
            "price_history": [
                {
                    "date": ph.change_date.isoformat(),
                    "price": float(ph.price),
                    "previous_price": float(ph.previous_price) if ph.previous_price else None,
                    "change_amount": float(ph.change_amount) if ph.change_amount is not None else None,
                    "change_percent": float(ph.change_percent) if ph.change_percent is not None else None,
                }
                for ph in l.price_history
            ],
        })

        if l.list_date:
            display_price = l.original_price or l.current_price
            timeline.append({
                "type": "listing",
                "date": l.list_date.isoformat(),
                "title": f"Listed on {l.source.value.title()} for ${float(display_price):,.0f}",
                "amount": float(display_price) if display_price else None,
                "details": {"source": l.source.value, "url": l.url},
            })

    timeline.sort(key=lambda x: x["date"] or "0000-00-00", reverse=True)

    return {
        "property": {
            "id": prop.id,
            "pin": prop.pin,
            "address": prop.address,
            "city": prop.city,
            "state": prop.state,
            "zip_code": prop.zip_code,
            "neighborhood": prop.neighborhood,
            "latitude": float(prop.latitude) if prop.latitude is not None else None,
            "longitude": float(prop.longitude) if prop.longitude is not None else None,
            "year_built": prop.year_built,
            "square_footage": float(prop.square_footage) if prop.square_footage is not None else None,
            "bedrooms": prop.bedrooms,
            "bathrooms": float(prop.bathrooms) if prop.bathrooms is not None else None,
            "market_value": float(prop.market_value) if prop.market_value is not None else None,
            "assessed_value": float(prop.assessed_value) if prop.assessed_value is not None else None,
            "property_type": prop.property_type,
        },
        "timeline": timeline,
        "listings": listings_out,
    }


@router.post("/", response_model=PropertyRead)
def create_property(payload: PropertyCreate, db: Session = Depends(get_db)):
    pin = normalize_pin(payload.pin)
    if pin:
        existing = db.query(Property).filter(Property.pin == pin).first()
        if existing:
            raise HTTPException(status_code=400, detail="Property with this PIN already exists")

    data = payload.model_dump()
    data["pin"] = pin
    data["address_normalized"] = normalize_address(data["address"])
    data["city"] = normalize_city(data["city"])

    prop = Property(**data)
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop
