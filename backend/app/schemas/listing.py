from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime
from app.models.listing import ListingStatus, ListingSource


class PriceHistoryRead(BaseModel):
    id: int
    change_date: date
    price: float
    previous_price: Optional[float] = None
    change_amount: Optional[float] = None
    change_percent: Optional[float] = None

    model_config = {"from_attributes": True}


class ListingBase(BaseModel):
    property_id: int
    source: ListingSource
    source_listing_id: Optional[str] = None
    url: Optional[str] = None
    status: ListingStatus = ListingStatus.active
    list_date: Optional[date] = None
    delisted_date: Optional[date] = None
    current_price: float
    original_price: Optional[float] = None
    days_on_market: Optional[int] = None
    price_per_sqft: Optional[float] = None
    listing_title: Optional[str] = None
    description: Optional[str] = None
    photo_url: Optional[str] = None
    mls_number: Optional[str] = None


class ListingCreate(ListingBase):
    pass


class ListingRead(ListingBase):
    id: int
    lowest_price: Optional[float] = None
    highest_price: Optional[float] = None
    price_drops_count: int = 0
    last_price_change_date: Optional[date] = None
    total_price_drop_amount: float = 0
    total_price_drop_pct: float = 0
    is_active: bool = True
    last_scraped_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ListingWithHistory(ListingRead):
    price_history: List[PriceHistoryRead] = []


class PriceDropSummary(BaseModel):
    listing_id: int
    property_id: int
    address: str
    city: str
    source: ListingSource
    url: Optional[str] = None
    current_price: float
    original_price: Optional[float] = None
    latest_drop_amount: Optional[float] = None
    latest_drop_pct: Optional[float] = None
    latest_drop_date: Optional[date] = None
    total_drops: int = 0
    total_drop_amount: float = 0
    total_drop_pct: float = 0
    days_on_market: Optional[int] = None
    photo_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    model_config = {"from_attributes": True}
