from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, UniqueConstraint, Index
from datetime import datetime
from app.database import Base


class BankFinancial(Base):
    """
    Per-bank, per-quarter snapshot from FDIC Call Reports.
    Used for Cook County (and any other county) drill-down.
    """
    __tablename__ = "bank_financials"

    id = Column(Integer, primary_key=True, index=True)

    # FDIC unique identifier (institution ID, sometimes called CERT)
    fdic_id = Column(String(20), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    city = Column(String(100), index=True)
    county = Column(String(100), index=True)
    state = Column(String(50), index=True)

    as_of_date = Column(Date, nullable=False, index=True)

    # Both values in $thousands (FDIC convention)
    total_assets = Column(Numeric(20, 2), nullable=False)
    oreo = Column(Numeric(20, 2), default=0, nullable=False)
    oreo_pct_assets = Column(Numeric(10, 6))   # derived: oreo / total_assets * 100

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("fdic_id", "as_of_date", name="uq_bank_financial_fdic_date"),
        Index("idx_bank_county_date", "county", "as_of_date"),
    )
