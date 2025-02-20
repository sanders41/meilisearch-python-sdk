from __future__ import annotations

from datetime import datetime

import pydantic
from camel_converter.pydantic_base import CamelBase

from meilisearch_python_sdk._utils import iso_to_date_time


class IndexBase(CamelBase):
    uid: str
    primary_key: str | None = None


class IndexInfo(IndexBase):
    created_at: datetime
    updated_at: datetime

    @pydantic.field_validator("created_at", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_created_at(cls, v: str) -> datetime:
        converted = iso_to_date_time(v)

        if not converted:  # pragma: no cover
            raise ValueError("created_at is required")

        return converted

    @pydantic.field_validator("updated_at", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_updated_at(cls, v: str) -> datetime:
        converted = iso_to_date_time(v)

        if not converted:  # pragma: no cover
            raise ValueError("updated_at is required")

        return converted


class IndexStats(CamelBase):
    number_of_documents: int
    number_of_embedded_documents: int | None = None
    number_of_embeddings: int | None = None
    is_indexing: bool
    field_distribution: dict[str, int]
