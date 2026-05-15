from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Date, Enum, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class ForeclosureStatus(str, enum.Enum):
    lis_pendens = "lis_pendens"
    judgment = "judgment"
    auction_scheduled = "auction_scheduled"
    sold_at_auction = "sold_at_auction"
    reo = "reo"
    dismissed = "dismissed"


class Foreclosure(Base):
    __tablename__ = "foreclosures"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)

    status = Column(Enum(ForeclosureStatus), nullable=False, index=True)
    filing_date = Column(Date, index=True)
    judgment_date = Column(Date)
    auction_date = Column(Date)
    sale_date = Column(Date)
    sale_price = Column(Numeric(14, 2))

    plaintiff = Column(String(255))
    defendant = Column(String(255))
    # No global-unique constraint: case numbers can legitimately repeat across
    # different counties / court systems and the column is nullable.
    # Dedup is via composite index (property_id, case_number).
    case_number = Column(String(50), index=True)
    court = Column(String(100), default="Cook County Circuit Court")
    original_loan_amount = Column(Numeric(14, 2))
    judgment_amount = Column(Numeric(14, 2))

    source = Column(String(100))
    source_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    property = relationship("Property", back_populates="foreclosures")

    __table_args__ = (
        Index("idx_foreclosure_prop_case", "property_id", "case_number"),
    )
