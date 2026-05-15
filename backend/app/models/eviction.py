from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Date, Enum, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class EvictionStatus(str, enum.Enum):
    filed = "filed"
    served = "served"
    judgment_for_plaintiff = "judgment_for_plaintiff"
    judgment_for_defendant = "judgment_for_defendant"
    dismissed = "dismissed"
    executed = "executed"


class Eviction(Base):
    __tablename__ = "evictions"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)

    status = Column(Enum(EvictionStatus), nullable=False, index=True)
    filing_date = Column(Date, index=True)
    hearing_date = Column(Date)
    judgment_date = Column(Date)
    execution_date = Column(Date)

    plaintiff = Column(String(255))
    defendant = Column(String(255))
    case_number = Column(String(50), index=True)
    court = Column(String(100), default="Cook County Circuit Court")
    eviction_reason = Column(String(255))
    monthly_rent = Column(Numeric(10, 2))
    amount_owed = Column(Numeric(12, 2))

    source = Column(String(100))
    source_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    property = relationship("Property", back_populates="evictions")

    __table_args__ = (
        Index("idx_eviction_prop_case", "property_id", "case_number"),
    )
