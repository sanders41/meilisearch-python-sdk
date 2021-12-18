from datetime import datetime
from typing import Any, Dict, Optional, Union

from camel_converter.pydantic_base import CamelBase
from pydantic import Field


class TaskId(CamelBase):
    uid: int


class TaskStatus(TaskId):
    index_uid: str
    status: str
    task_type: Union[str, Dict[str, Any]] = Field(..., alias="type")
    details: Optional[Dict[str, Any]]
    duration: Optional[str]
    enqueued_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
