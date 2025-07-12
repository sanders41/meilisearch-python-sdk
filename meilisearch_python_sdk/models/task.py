from __future__ import annotations

from datetime import datetime

import pydantic
from camel_converter.pydantic_base import CamelBase
from pydantic import Field

from meilisearch_python_sdk._utils import iso_to_date_time
from meilisearch_python_sdk.types import JsonDict


class TaskId(CamelBase):
    uid: int


class TaskResult(TaskId):
    index_uid: str | None = None
    status: str
    task_type: str | JsonDict = Field(..., alias="type")
    details: JsonDict | None = None
    error: JsonDict | None = None
    canceled_by: int | None = None
    duration: str | None = None
    enqueued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    batch_uid: int | None = None

    @pydantic.field_validator("enqueued_at", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_enqueued_at(cls, v: str) -> datetime:
        converted = iso_to_date_time(v)

        if not converted:  # pragma: no cover
            raise ValueError("enqueued_at is required")

        return converted

    @pydantic.field_validator("started_at", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_started_at(cls, v: str) -> datetime | None:
        return iso_to_date_time(v)

    @pydantic.field_validator("finished_at", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_finished_at(cls, v: str) -> datetime | None:
        return iso_to_date_time(v)


class TaskStatus(CamelBase):
    results: list[TaskResult]
    total: int
    limit: int
    from_: int | None = Field(None, alias="from")
    next: int | None = None


class TaskInfo(CamelBase):
    task_uid: int
    index_uid: str | None = None
    status: str
    task_type: str | JsonDict = Field(..., alias="type")
    enqueued_at: datetime
    batch_uid: int | None = None

    @pydantic.field_validator("enqueued_at", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_enqueued_at(cls, v: str) -> datetime:
        converted = iso_to_date_time(v)

        if not converted:  # pragma: no cover
            raise ValueError("enqueued_at is required")

        return converted
