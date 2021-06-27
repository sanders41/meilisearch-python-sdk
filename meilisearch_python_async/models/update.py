from datetime import datetime
from typing import Dict, Optional

from camel_converter.pydantic_base import CamelBase
from pydantic import Field


class UpdateId(CamelBase):
    update_id: int


class UpdateStatus(CamelBase):
    status: str
    update_id: int
    update_type: Dict = Field(..., alias="type")
    enqueued_at: datetime
    duration: Optional[float] = None
    processed_at: Optional[datetime] = None
    error: Optional[str] = None
