from datetime import datetime
from typing import List, Optional, Union

import pydantic
from camel_converter.pydantic_base import CamelBase
from pydantic import Field

from meilisearch_python_sdk._utils import iso_to_date_time
from meilisearch_python_sdk.types import JsonDict


class TaskId(CamelBase):
    uid: int


class TaskResult(TaskId):
    index_uid: Optional[str] = None
    status: str
    task_type: Union[str, JsonDict] = Field(..., alias="type")
    details: Optional[JsonDict] = None
    error: Optional[JsonDict] = None
    canceled_by: Optional[int] = None
    duration: Optional[str] = None
    enqueued_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @pydantic.field_validator("enqueued_at", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_enqueued_at(cls, v: str) -> datetime:
        converted = iso_to_date_time(v)

        if not converted:  # pragma: no cover
            raise ValueError("enqueued_at is required")

        return converted

    @pydantic.field_validator("started_at", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_started_at(cls, v: str) -> Union[datetime, None]:
        return iso_to_date_time(v)

    @pydantic.field_validator("finished_at", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_finished_at(cls, v: str) -> Union[datetime, None]:
        return iso_to_date_time(v)


class TaskStatus(CamelBase):
    results: List[TaskResult]
    total: int
    limit: int
    from_: int = Field(..., alias="from")
    next: Optional[int] = None


class TaskInfo(CamelBase):
    task_uid: int
    index_uid: Optional[str] = None
    status: str
    task_type: Union[str, JsonDict] = Field(..., alias="type")
    enqueued_at: datetime

    @pydantic.field_validator("enqueued_at", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_enqueued_at(cls, v: str) -> datetime:
        converted = iso_to_date_time(v)

        if not converted:  # pragma: no cover
            raise ValueError("enqueued_at is required")

        return converted
