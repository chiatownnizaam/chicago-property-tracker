from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Date, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)

    sale_date = Column(Date, nullable=False, index=True)
    sale_price = Column(Numeric(14, 2), nullable=False)
    price_per_sqft = Column(Numeric(10, 2))
    seller_name = Column(String(255))
    buyer_name = Column(String(255))
    deed_type = Column(String(100))
    # Document number is the natural key from the Recorder — when present it
    # makes a sale globally unique across the dataset.
    document_number = Column(String(50), index=True)

    source = Column(String(100), default="Cook County Recorder")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    property = relationship("Property", back_populates="sales")

    __table_args__ = (
        # Dedup: same property + same date + same price is the same sale.
        # Use this for app-level upsert lookups.
        Index("idx_sale_property_date_price", "property_id", "sale_date", "sale_price"),
        # When the recorder doc_no is present, treat it as the unique sale key.
        UniqueConstraint("document_number", name="uq_sale_doc_number"),
    )
