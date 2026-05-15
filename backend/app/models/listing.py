from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Date, Enum, Boolean, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class ListingStatus(str, enum.Enum):
    active = "active"
    pending = "pending"
    contingent = "contingent"
    sold = "sold"
    off_market = "off_market"
    withdrawn = "withdrawn"


class ListingSource(str, enum.Enum):
    redfin = "redfin"
    realtor = "realtor"
    zillow = "zillow"
    trulia = "trulia"
    mls = "mls"
    other = "other"


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)

    source = Column(Enum(ListingSource), nullable=False, index=True)
    source_listing_id = Column(String(100), index=True)
    url = Column(String(500))

    status = Column(Enum(ListingStatus), default=ListingStatus.active, index=True, nullable=False)
    list_date = Column(Date, index=True)
    delisted_date = Column(Date)

    current_price = Column(Numeric(14, 2), nullable=False)
    original_price = Column(Numeric(14, 2))
    lowest_price = Column(Numeric(14, 2))
    highest_price = Column(Numeric(14, 2))

    days_on_market = Column(Integer)
    price_per_sqft = Column(Numeric(10, 2))

    listing_title = Column(String(255))
    description = Column(String(2000))
    photo_url = Column(String(500))
    mls_number = Column(String(50))

    price_drops_count = Column(Integer, default=0, nullable=False)
    last_price_change_date = Column(Date)
    total_price_drop_amount = Column(Numeric(14, 2), default=0, nullable=False)
    total_price_drop_pct = Column(Numeric(6, 2), default=0, nullable=False)

    is_active = Column(Boolean, default=True, index=True, nullable=False)
    last_scraped_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    property = relationship("Property", back_populates="listings")
    price_history = relationship(
        "PriceHistory",
        back_populates="listing",
        cascade="all, delete-orphan",
        order_by="PriceHistory.change_date.desc()",
    )

    __table_args__ = (
        # Source + external id = the natural key for a listing. Stronger than
        # a plain index since we want hard upsert guarantees.
        UniqueConstraint("source", "source_listing_id", name="uq_listing_source_external_id"),
        Index("idx_listing_status_active", "status", "is_active"),
    )


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True)

    change_date = Column(Date, nullable=False, index=True)
    price = Column(Numeric(14, 2), nullable=False)
    previous_price = Column(Numeric(14, 2))
    change_amount = Column(Numeric(14, 2))
    change_percent = Column(Numeric(6, 2))

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    listing = relationship("Listing", back_populates="price_history")

    __table_args__ = (
        # One price-change record per listing per day. Same-day duplicates
        # are dropped.
        UniqueConstraint("listing_id", "change_date", name="uq_pricehistory_listing_date"),
    )
