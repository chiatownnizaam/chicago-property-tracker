from pydantic import BaseModel
from typing import Optional


class PropertyMini(BaseModel):
    """Minimal property identifier embedded in event responses."""
    id: int
    address: str
    city: str
    zip_code: Optional[str] = None

    model_config = {"from_attributes": True}
