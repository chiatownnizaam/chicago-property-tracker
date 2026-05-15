from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, contains_eager
from typing import Optional
from datetime import date
from app.database import get_db
from app.models.sale import Sale
from app.models.property import Property
from app.schemas.sale import SaleCreate, SaleRead
from app.constants import TRACKED_CITIES

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("/", response_model=list[SaleRead])
def list_sales(
    city: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Sale)
        .join(Property, Sale.property_id == Property.id)
        .options(contains_eager(Sale.property))
        .filter(Property.city.in_(TRACKED_CITIES))
    )
    if city:
        query = query.filter(Property.city.ilike(f"%{city}%"))
    if date_from:
        query = query.filter(Sale.sale_date >= date_from)
    if date_to:
        query = query.filter(Sale.sale_date <= date_to)
    if min_price:
        query = query.filter(Sale.sale_price >= min_price)
    if max_price:
        query = query.filter(Sale.sale_price <= max_price)

    return query.order_by(Sale.sale_date.desc()).offset(offset).limit(limit).all()


@router.get("/{sale_id}", response_model=SaleRead)
def get_sale(sale_id: int, db: Session = Depends(get_db)):
    record = db.query(Sale).filter(Sale.id == sale_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Sale record not found")
    return record


@router.post("/", response_model=SaleRead)
def create_sale(payload: SaleCreate, db: Session = Depends(get_db)):
    prop = db.query(Property).filter(Property.id == payload.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    record = Sale(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
