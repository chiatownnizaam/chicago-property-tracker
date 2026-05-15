from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, contains_eager
from typing import Optional
from datetime import date
from app.database import get_db
from app.models.foreclosure import Foreclosure, ForeclosureStatus
from app.models.property import Property
from app.schemas.foreclosure import ForeclosureCreate, ForeclosureRead
from app.constants import TRACKED_CITIES

router = APIRouter(prefix="/foreclosures", tags=["foreclosures"])


@router.get("/", response_model=list[ForeclosureRead])
def list_foreclosures(
    city: Optional[str] = Query(None),
    status: Optional[ForeclosureStatus] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Foreclosure)
        .join(Property, Foreclosure.property_id == Property.id)
        .options(contains_eager(Foreclosure.property))
        .filter(Property.city.in_(TRACKED_CITIES))
    )
    if city:
        query = query.filter(Property.city.ilike(f"%{city}%"))
    if status:
        query = query.filter(Foreclosure.status == status)
    if date_from:
        query = query.filter(Foreclosure.filing_date >= date_from)
    if date_to:
        query = query.filter(Foreclosure.filing_date <= date_to)

    return query.order_by(Foreclosure.filing_date.desc()).offset(offset).limit(limit).all()


@router.get("/{foreclosure_id}", response_model=ForeclosureRead)
def get_foreclosure(foreclosure_id: int, db: Session = Depends(get_db)):
    record = db.query(Foreclosure).filter(Foreclosure.id == foreclosure_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Foreclosure record not found")
    return record


@router.post("/", response_model=ForeclosureRead)
def create_foreclosure(payload: ForeclosureCreate, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == payload.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    record = Foreclosure(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
