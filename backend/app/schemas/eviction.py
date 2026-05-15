from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from app.models.eviction import EvictionStatus
from app.schemas.common import PropertyMini


class EvictionBase(BaseModel):
    property_id: int
    status: EvictionStatus
    filing_date: Optional[date] = None
    hearing_date: Optional[date] = None
    judgment_date: Optional[date] = None
    execution_date: Optional[date] = None
    plaintiff: Optional[str] = None
    defendant: Optional[str] = None
    case_number: Optional[str] = None
    court: Optional[str] = "Cook County Circuit Court"
    eviction_reason: Optional[str] = None
    monthly_rent: Optional[float] = None
    amount_owed: Optional[float] = None
    source: Optional[str] = None
    source_url: Optional[str] = None


class EvictionCreate(EvictionBase):
    pass


class EvictionRead(EvictionBase):
    id: int
    created_at: datetime
    updated_at: datetime
    property: Optional[PropertyMini] = None

    model_config = {"from_attributes": True}
