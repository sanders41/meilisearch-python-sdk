from __future__ import annotations

from datetime import datetime

from camel_converter.pydantic_base import CamelBase
from pydantic import Field, field_validator

from meilisearch_python_sdk._utils import iso_to_date_time
from meilisearch_python_sdk.types import JsonDict


class BatchId(CamelBase):
    uid: int


class Status(CamelBase):
    succeeded: int | None = None
    failed: int | None = None
    cancelled: int | None = None
    processing: int | None = None
    enqueued: int | None = None


class Stats(CamelBase):
    total_nb_tasks: int
    status: Status
    batch_types: JsonDict | None = Field(None, alias="types")
    index_uids: JsonDict | None = None
    progress_trace: JsonDict | None = None
    write_channel_congestion: JsonDict | None = None
    internal_database_sizes: JsonDict | None = None


class BatchResult(BatchId):
    details: JsonDict | None = None
    progress: JsonDict | None = None
    stats: Stats
    duration: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @field_validator("started_at", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_started_at(cls, v: str) -> datetime | None:
        return iso_to_date_time(v)

    @field_validator("finished_at", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_finished_at(cls, v: str) -> datetime | None:
        return iso_to_date_time(v)


class BatchStatus(CamelBase):
    results: list[BatchResult]
    total: int
    limit: int
    from_: int | None = Field(None, alias="from")
    next: int | None = None
