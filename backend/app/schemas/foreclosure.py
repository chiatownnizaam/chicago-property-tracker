from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from app.models.foreclosure import ForeclosureStatus
from app.schemas.common import PropertyMini


class ForeclosureBase(BaseModel):
    property_id: int
    status: ForeclosureStatus
    filing_date: Optional[date] = None
    judgment_date: Optional[date] = None
    auction_date: Optional[date] = None
    sale_date: Optional[date] = None
    sale_price: Optional[float] = None
    plaintiff: Optional[str] = None
    defendant: Optional[str] = None
    case_number: Optional[str] = None
    court: Optional[str] = "Cook County Circuit Court"
    original_loan_amount: Optional[float] = None
    judgment_amount: Optional[float] = None
    source: Optional[str] = None
    source_url: Optional[str] = None


class ForeclosureCreate(ForeclosureBase):
    pass


class ForeclosureRead(ForeclosureBase):
    id: int
    created_at: datetime
    updated_at: datetime
    property: Optional[PropertyMini] = None

    model_config = {"from_attributes": True}
