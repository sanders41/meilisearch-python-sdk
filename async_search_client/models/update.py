from datetime import datetime
from typing import Dict, Optional

from pydantic import Field

from async_search_client.models.base_config import BaseConfig


class UpdateId(BaseConfig):
    update_id: int


class UpdateStatus(BaseConfig):
    status: str
    update_id: int
    update_type: Dict = Field(..., alias="type")
    enqueued_at: datetime
    duration: Optional[float] = None
    processed_at: Optional[datetime] = None
    error: Optional[str] = None
