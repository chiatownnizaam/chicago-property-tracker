from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from app.models.bank_seizure import SeizureType
from app.schemas.common import PropertyMini


class BankSeizureBase(BaseModel):
    property_id: int
    seizure_type: SeizureType
    seizure_date: Optional[date] = None
    release_date: Optional[date] = None
    seizing_entity: Optional[str] = None
    seizing_entity_type: Optional[str] = None
    tax_delinquency_amount: Optional[float] = None
    lien_amount: Optional[float] = None
    assessed_value_at_seizure: Optional[float] = None
    case_number: Optional[str] = None
    document_number: Optional[str] = None
    is_active: Optional[int] = 1
    source: Optional[str] = None
    source_url: Optional[str] = None


class BankSeizureCreate(BankSeizureBase):
    pass


class BankSeizureRead(BankSeizureBase):
    id: int
    created_at: datetime
    updated_at: datetime
    property: Optional[PropertyMini] = None

    model_config = {"from_attributes": True}
