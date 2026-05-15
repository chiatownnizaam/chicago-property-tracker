from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from datetime import date, timedelta
from app.database import get_db
from app.models.listing import Listing, ListingStatus, ListingSource
from app.models.property import Property
from app.schemas.listing import ListingRead, ListingWithHistory, PriceDropSummary
from app.constants import TRACKED_CITIES

router = APIRouter(prefix="/listings", tags=["listings"])


@router.get("/", response_model=list[ListingRead])
def list_listings(
    city: Optional[str] = Query(None),
    source: Optional[ListingSource] = Query(None),
    status: Optional[ListingStatus] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    is_active: Optional[bool] = Query(True),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Listing)
        .join(Property)
        .filter(Property.city.in_(TRACKED_CITIES))
    )
    if city:
        query = query.filter(Property.city.ilike(f"%{city}%"))
    if source:
        query = query.filter(Listing.source == source)
    if status:
        query = query.filter(Listing.status == status)
    if min_price:
        query = query.filter(Listing.current_price >= min_price)
    if max_price:
        query = query.filter(Listing.current_price <= max_price)
    if is_active is not None:
        query = query.filter(Listing.is_active == is_active)

    return query.order_by(desc(Listing.last_scraped_at)).offset(offset).limit(limit).all()


@router.get("/price-drops", response_model=list[PriceDropSummary])
def price_drops(
    city: Optional[str] = Query(None),
    source: Optional[ListingSource] = Query(None),
    days: int = Query(30, ge=1, le=365, description="Look back this many days"),
    min_drop_pct: Optional[float] = Query(None, description="Minimum total drop percent"),
    min_drop_amount: Optional[float] = Query(None, description="Minimum total drop in dollars"),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    """Listings with one or more price drops in the trailing window."""
    cutoff = date.today() - timedelta(days=days)
    query = (
        db.query(Listing, Property)
        .join(Property, Listing.property_id == Property.id)
        .filter(Property.city.in_(TRACKED_CITIES))
        .filter(Listing.price_drops_count > 0)
        .filter(Listing.last_price_change_date >= cutoff)
    )
    if city:
        query = query.filter(Property.city.ilike(f"%{city}%"))
    if source:
        query = query.filter(Listing.source == source)
    if min_drop_pct is not None:
        query = query.filter(Listing.total_price_drop_pct >= min_drop_pct)
    if min_drop_amount is not None:
        query = query.filter(Listing.total_price_drop_amount >= min_drop_amount)

    rows = query.order_by(desc(Listing.total_price_drop_pct)).limit(limit).all()

    results = []
    for listing, prop in rows:
        latest = (listing.price_history[0] if listing.price_history else None)
        results.append(PriceDropSummary(
            listing_id=listing.id,
            property_id=prop.id,
            address=prop.address,
            city=prop.city,
            source=listing.source,
            url=listing.url,
            current_price=listing.current_price,
            original_price=listing.original_price,
            latest_drop_amount=latest.change_amount if latest else None,
            latest_drop_pct=latest.change_percent if latest else None,
            latest_drop_date=latest.change_date if latest else None,
            total_drops=listing.price_drops_count or 0,
            total_drop_amount=listing.total_price_drop_amount or 0,
            total_drop_pct=listing.total_price_drop_pct or 0,
            days_on_market=listing.days_on_market,
            photo_url=listing.photo_url,
            latitude=prop.latitude,
            longitude=prop.longitude,
        ))
    return results


@router.get("/{listing_id}", response_model=ListingWithHistory)
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing
