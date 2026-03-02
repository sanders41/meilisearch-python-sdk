from __future__ import annotations

from datetime import datetime

import pydantic
from camel_converter.pydantic_base import CamelBase


class IndexBase(CamelBase):
    uid: str
    primary_key: str | None = None


class IndexInfo(IndexBase):
    created_at: datetime
    updated_at: datetime

    @pydantic.field_validator("created_at", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_created_at(cls, v: str | datetime) -> datetime:
        if isinstance(v, str):
            return datetime.fromisoformat(v)

        return v

    @pydantic.field_validator("updated_at", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_updated_at(cls, v: str | datetime) -> datetime:
        if isinstance(v, str):
            return datetime.fromisoformat(v)

        return v


class IndexStats(CamelBase):
    number_of_documents: int
    number_of_embedded_documents: int | None = None
    number_of_embeddings: int | None = None
    is_indexing: bool
    field_distribution: dict[str, int]


class FieldsFilter(CamelBase):
    attribute_patterns: str | None = None
    displayed: bool | None = None
    sortable: bool | None = None
    searchable: bool | None = None
    ranking_rule: bool | None = None
    filterable: bool | None = None


class FieldDisplayConfig(CamelBase):
    enabled: bool


class FieldSearchConfig(CamelBase):
    enabled: bool


class FieldSortableConfig(CamelBase):
    enabled: bool


class FieldRankingRuleConfig(CamelBase):
    order: str | None = None


class FieldDistinctConfig(CamelBase):
    enabled: bool


class FieldFilterableConfig(CamelBase):
    enabled: bool
    sort_by: str
    facet_search: bool
    equality: bool
    comparison: bool


class FieldLocalizedConfig(CamelBase):
    locales: list[str]


class Field(CamelBase):
    name: str
    displayed: FieldDisplayConfig
    searchable: FieldSearchConfig
    sortable: FieldSortableConfig
    distinct: FieldDistinctConfig
    ranking_rule: FieldRankingRuleConfig
    filterable: FieldFilterableConfig
    localized: FieldLocalizedConfig


class FieldResults(CamelBase):
    fields: list[Field]
    offset: int
    limit: int
    total: int
