from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

import pydantic
from camel_converter.pydantic_base import CamelBase

from meilisearch_python_sdk.models.index import IndexStats


class ClientStats(CamelBase):
    database_size: int
    used_database_size: int | None = None
    last_update: datetime | None = None
    indexes: dict[str, IndexStats] | None = None


class _KeyBase(CamelBase):
    uid: str
    name: str | None = None
    description: str | None = None
    actions: list[str]
    indexes: list[str]
    expires_at: datetime | None = None

    model_config = pydantic.ConfigDict(ser_json_timedelta="iso8601")  # type: ignore[typeddict-unknown-key]


class Key(_KeyBase):
    key: str
    created_at: datetime
    updated_at: datetime | None = None


class KeyCreate(CamelBase):
    name: str | None = None
    description: str | None = None
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


class Remote(CamelBase):
    url: str | None = None
    search_api_key: str | None = None


class Network(CamelBase):
    self_: str | None = pydantic.Field(None, alias="self")
    remotes: Mapping[str, Remote] | None = None
