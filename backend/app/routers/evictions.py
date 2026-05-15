from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, contains_eager
from typing import Optional
from datetime import date
from app.database import get_db
from app.models.eviction import Eviction, EvictionStatus
from app.models.property import Property
from app.schemas.eviction import EvictionCreate, EvictionRead
from app.constants import TRACKED_CITIES

router = APIRouter(prefix="/evictions", tags=["evictions"])


@router.get("/", response_model=list[EvictionRead])
def list_evictions(
    city: Optional[str] = Query(None),
    status: Optional[EvictionStatus] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Eviction)
        .join(Property, Eviction.property_id == Property.id)
        .options(contains_eager(Eviction.property))
        .filter(Property.city.in_(TRACKED_CITIES))
    )
    if city:
        query = query.filter(Property.city.ilike(f"%{city}%"))
    if status:
        query = query.filter(Eviction.status == status)
    if date_from:
        query = query.filter(Eviction.filing_date >= date_from)
    if date_to:
        query = query.filter(Eviction.filing_date <= date_to)

    return query.order_by(Eviction.filing_date.desc()).offset(offset).limit(limit).all()


@router.get("/{eviction_id}", response_model=EvictionRead)
def get_eviction(eviction_id: int, db: Session = Depends(get_db)):
    record = db.query(Eviction).filter(Eviction.id == eviction_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Eviction record not found")
    return record


@router.post("/", response_model=EvictionRead)
def create_eviction(payload: EvictionCreate, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == payload.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    record = Eviction(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
