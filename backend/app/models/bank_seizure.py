from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Date, Enum, Boolean, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class SeizureType(str, enum.Enum):
    tax_lien = "tax_lien"
    tax_sale = "tax_sale"
    reo = "reo"
    hud = "hud"
    fdic = "fdic"
    city_owned = "city_owned"
    county_owned = "county_owned"


class BankSeizure(Base):
    __tablename__ = "bank_seizures"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)

    seizure_type = Column(Enum(SeizureType), nullable=False, index=True)
    seizure_date = Column(Date, index=True)
    release_date = Column(Date)

    seizing_entity = Column(String(255))
    seizing_entity_type = Column(String(50))
    tax_delinquency_amount = Column(Numeric(14, 2))
    lien_amount = Column(Numeric(14, 2))
    assessed_value_at_seizure = Column(Numeric(14, 2))

    case_number = Column(String(50), index=True)
    document_number = Column(String(50))
    is_active = Column(Boolean, default=True, nullable=False)

    source = Column(String(100))
    source_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    property = relationship("Property", back_populates="bank_seizures")

    __table_args__ = (
        Index("idx_seizure_prop_type_year", "property_id", "seizure_type", "case_number"),
    )
