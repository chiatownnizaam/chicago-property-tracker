from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, contains_eager
from typing import Optional
from datetime import date
from app.database import get_db
from app.models.bank_seizure import BankSeizure, SeizureType
from app.models.property import Property
from app.schemas.bank_seizure import BankSeizureCreate, BankSeizureRead
from app.constants import TRACKED_CITIES

router = APIRouter(prefix="/bank-seizures", tags=["bank_seizures"])


@router.get("/", response_model=list[BankSeizureRead])
def list_bank_seizures(
    city: Optional[str] = Query(None),
    seizure_type: Optional[SeizureType] = Query(None),
    is_active: Optional[bool] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    query = (
        db.query(BankSeizure)
        .join(Property, BankSeizure.property_id == Property.id)
        .options(contains_eager(BankSeizure.property))
        .filter(Property.city.in_(TRACKED_CITIES))
    )
    if city:
        query = query.filter(Property.city.ilike(f"%{city}%"))
    if seizure_type:
        query = query.filter(BankSeizure.seizure_type == seizure_type)
    if is_active is not None:
        query = query.filter(BankSeizure.is_active == (1 if is_active else 0))
    if date_from:
        query = query.filter(BankSeizure.seizure_date >= date_from)
    if date_to:
        query = query.filter(BankSeizure.seizure_date <= date_to)

    return query.order_by(BankSeizure.seizure_date.desc()).offset(offset).limit(limit).all()


@router.get("/{seizure_id}", response_model=BankSeizureRead)
def get_bank_seizure(seizure_id: int, db: Session = Depends(get_db)):
    record = db.query(BankSeizure).filter(BankSeizure.id == seizure_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Bank seizure record not found")
    return record


@router.post("/", response_model=BankSeizureRead)
def create_bank_seizure(payload: BankSeizureCreate, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == payload.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    record = BankSeizure(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
