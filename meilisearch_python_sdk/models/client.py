from __future__ import annotations

from datetime import datetime

import pydantic
from camel_converter.pydantic_base import CamelBase

from meilisearch_python_sdk._utils import iso_to_date_time
from meilisearch_python_sdk.models.index import IndexStats


class ClientStats(CamelBase):
    database_size: int
    last_update: datetime | None = None
    indexes: dict[str, IndexStats] | None = None

    @pydantic.field_validator("last_update", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_last_update(cls, v: str) -> datetime | None:
        return iso_to_date_time(v)


class _KeyBase(CamelBase):
    uid: str
    name: str | None = None
    description: str
    actions: list[str]
    indexes: list[str]
    expires_at: datetime | None = None

    model_config = pydantic.ConfigDict(ser_json_timedelta="iso8601")  # type: ignore[typeddict-unknown-key]

    @pydantic.field_validator("expires_at", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_expires_at(cls, v: str) -> datetime | None:
        return iso_to_date_time(v)


class Key(_KeyBase):
    key: str
    created_at: datetime
    updated_at: datetime | None = None

    @pydantic.field_validator("created_at", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_created_at(cls, v: str) -> datetime:
        converted = iso_to_date_time(v)

        if not converted:  # pragma: no cover
            raise ValueError("created_at is required")

        return converted

    @pydantic.field_validator("updated_at", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_updated_at(cls, v: str) -> datetime | None:
        return iso_to_date_time(v)


class KeyCreate(CamelBase):
    name: str | None = None
    description: str
    actions: list[str]
    indexes: list[str]
    expires_at: datetime | None = None

    model_config = pydantic.ConfigDict(ser_json_timedelta="iso8601")  # type: ignore[typeddict-unknown-key]


class KeyUpdate(CamelBase):
    key: str
    name: str | None = None
    description: str | None = None
    actions: list[str] | None = None
    indexes: list[str] | None = None
    expires_at: datetime | None = None

    model_config = pydantic.ConfigDict(ser_json_timedelta="iso8601")  # type: ignore[typeddict-unknown-key]


class KeySearch(CamelBase):
    results: list[Key]
    offset: int
    limit: int
    total: int
