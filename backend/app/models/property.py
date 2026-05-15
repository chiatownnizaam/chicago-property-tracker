from sqlalchemy import Column, Integer, String, Numeric, DateTime, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from app.constants import TRACKED_CITIES as TRACKED_MUNICIPALITIES  # noqa: F401


class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    # PIN stored digits-only (normalized) so all formats dedupe to one row.
    pin = Column(String(20), unique=True, index=True)
    # `address` is the display form. `address_normalized` is the dedup key.
    address = Column(String(255), nullable=False)
    address_normalized = Column(String(255), nullable=False, index=True)
    city = Column(String(100), nullable=False)
    state = Column(String(2), default="IL", nullable=False)
    zip_code = Column(String(10))
    neighborhood = Column(String(100))
    municipality = Column(String(100))

    property_class = Column(String(10))
    property_type = Column(String(50))
    year_built = Column(Integer)
    square_footage = Column(Numeric(10, 2))
    bedrooms = Column(Integer)
    bathrooms = Column(Numeric(4, 1))
    lot_size = Column(Numeric(10, 4))

    assessed_value = Column(Numeric(14, 2))
    market_value = Column(Numeric(14, 2))
    tax_year = Column(Integer)

    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))

    # FEMA National Flood Hazard Layer enrichment
    flood_zone = Column(String(20))
    flood_zone_subtype = Column(String(100))
    flood_zone_updated_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    sales = relationship("Sale", back_populates="property", cascade="all, delete-orphan")
    foreclosures = relationship("Foreclosure", back_populates="property", cascade="all, delete-orphan")
    evictions = relationship("Eviction", back_populates="property", cascade="all, delete-orphan")
    bank_seizures = relationship("BankSeizure", back_populates="property", cascade="all, delete-orphan")
    listings = relationship("Listing", back_populates="property", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_property_city", "city"),
        Index("idx_property_municipality", "municipality"),
        Index("idx_property_latlon", "latitude", "longitude"),
        # Dedup key: same normalized address + city = same property
        Index("uq_property_addr_city", "address_normalized", "city", unique=True),
    )
