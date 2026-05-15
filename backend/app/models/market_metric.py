from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, UniqueConstraint, Index, JSON
from datetime import datetime
from app.database import Base


class MarketMetric(Base):
    """
    Cached time-series of macro market metrics (mostly FRED).
    One row = one observation of one series at one geography on one date.
    """
    __tablename__ = "market_metrics"

    id = Column(Integer, primary_key=True, index=True)

    source = Column(String(20), nullable=False, index=True)         # "fred" | "computed"
    series_id = Column(String(50), nullable=False, index=True)      # e.g. "DRSFRMACBS"
    series_name = Column(String(255), nullable=False)
    geography = Column(String(50), nullable=False, default="national")  # national, illinois, tracked

    as_of_date = Column(Date, nullable=False, index=True)
    value = Column(Numeric(14, 6), nullable=False)
    unit = Column(String(20), default="percent")                    # percent | count | ratio | usd
    frequency = Column(String(20))                                  # daily | weekly | monthly | quarterly | annual

    series_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("source", "series_id", "geography", "as_of_date",
                         name="uq_market_metric_obs"),
        Index("idx_market_metric_series_date", "series_id", "as_of_date"),
    )
