from datetime import datetime
from typing import Any, Dict, Optional, Union

from camel_converter.pydantic_base import CamelBase
from pydantic import Field


class UpdateId(CamelBase):
    update_id: int


class UpdateStatus(CamelBase):
    status: str
    update_id: int
    update_type: Union[str, Dict[str, Any]] = Field(..., alias="type")
    enqueued_at: datetime
    duration: Optional[float] = None
    processed_at: Optional[datetime] = None
    message: Optional[str] = None
    code: Optional[str] = None
    link: Optional[str] = None
