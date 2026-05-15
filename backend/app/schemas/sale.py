from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from app.schemas.common import PropertyMini


class SaleBase(BaseModel):
    property_id: int
    sale_date: date
    sale_price: float
    price_per_sqft: Optional[float] = None
    seller_name: Optional[str] = None
    buyer_name: Optional[str] = None
    deed_type: Optional[str] = None
    document_number: Optional[str] = None
    source: Optional[str] = "Cook County Recorder"


class SaleCreate(SaleBase):
    pass


class SaleRead(SaleBase):
    id: int
    created_at: datetime
    property: Optional[PropertyMini] = None

    model_config = {"from_attributes": True}
