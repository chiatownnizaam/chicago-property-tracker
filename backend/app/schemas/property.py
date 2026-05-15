from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PropertyBase(BaseModel):
    pin: Optional[str] = None
    address: str
    city: str
    state: str = "IL"
    zip_code: Optional[str] = None
    neighborhood: Optional[str] = None
    municipality: Optional[str] = None
    property_class: Optional[str] = None
    property_type: Optional[str] = None
    year_built: Optional[int] = None
    square_footage: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    lot_size: Optional[float] = None
    assessed_value: Optional[float] = None
    market_value: Optional[float] = None
    tax_year: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class PropertyCreate(PropertyBase):
    pass


class PropertyRead(PropertyBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PropertySummary(BaseModel):
    id: int
    pin: Optional[str] = None
    address: str
    city: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    market_value: Optional[float] = None
    has_foreclosure: bool = False
    has_eviction: bool = False
    has_bank_seizure: bool = False
    last_sale_price: Optional[float] = None
    last_sale_date: Optional[str] = None

    model_config = {"from_attributes": True}
