from __future__ import annotations

from enum import Enum

import pydantic
from camel_converter.pydantic_base import CamelBase

from meilisearch_python_sdk.types import JsonDict


class MinWordSizeForTypos(CamelBase):
    one_typo: int | None = None
    two_typos: int | None = None


class TypoTolerance(CamelBase):
    enabled: bool = True
    disable_on_attributes: list[str] | None = None
    disable_on_words: list[str] | None = None
    min_word_size_for_typos: MinWordSizeForTypos | None = None


class Faceting(CamelBase):
    max_values_per_facet: int
    sort_facet_values_by: dict[str, str] | None = None

    @pydantic.field_validator("sort_facet_values_by")  # type: ignore[attr-defined]
    @classmethod
    def validate_facet_order(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if not v:  # pragma: no cover
            return None

        for _, value in v.items():
            if value not in ("alpha", "count"):
                raise ValueError('facet_order must be either "alpha" or "count"')

        return v


class Pagination(CamelBase):
    max_total_hits: int


class Distribution(CamelBase):
    mean: float
    sigma: float


class OpenAiEmbedder(CamelBase):
    source: str = "openAi"
    model: str | None = None  # Defaults to text-embedding-ada-002
    dimensions: int | None = None  # Uses the model default
    api_key: str | None = None  # Can be provided through a CLI option or environment variable
    document_template: str | None = None
    distribution: Distribution | None = None


class HuggingFaceEmbedder(CamelBase):
    source: str = "huggingFace"
    model: str | None = None  # Defaults to BAAI/bge-base-en-v1.5
    revision: str | None = None
    document_template: str | None = None
    distribution: Distribution | None = None


class OllamaEmbedder(CamelBase):
    source: str = "ollama"
    url: str | None = None
    api_key: str | None = None
    model: str
    document_template: str | None = None
    distribution: Distribution | None = None


class RestEmbedder(CamelBase):
    source: str = "rest"
    url: str
    api_key: str | None = None
    dimensions: int
    document_template: str | None = None
    input_field: list[str] | None = None
    input_type: str = "text"
    query: JsonDict = {}
    path_to_embeddings: list[str] | None = None
    embedding_object: list[str] | None = None
    distribution: Distribution | None = None


class UserProvidedEmbedder(CamelBase):
    source: str = "userProvided"
    dimensions: int
    distribution: Distribution | None = None


class Embedders(CamelBase):
    embedders: dict[
        str,
        OpenAiEmbedder | HuggingFaceEmbedder | OllamaEmbedder | RestEmbedder | UserProvidedEmbedder,
    ]


class ProximityPrecision(str, Enum):
    BY_WORD = "byWord"
    BY_ATTRIBUTE = "byAttribute"


class MeilisearchSettings(CamelBase):
    synonyms: JsonDict | None = None
    stop_words: list[str] | None = None
    ranking_rules: list[str] | None = None
    filterable_attributes: list[str] | None = None
    distinct_attribute: str | None = None
    searchable_attributes: list[str] | None = None
    displayed_attributes: list[str] | None = None
    sortable_attributes: list[str] | None = None
    typo_tolerance: TypoTolerance | None = None
    faceting: Faceting | None = None
    pagination: Pagination | None = None
    proximity_precision: ProximityPrecision | None = None
    separator_tokens: list[str] | None = None
    non_separator_tokens: list[str] | None = None
    search_cutoff_ms: int | None = None
    dictionary: list[str] | None = None
    embedders: (
        dict[
            str,
            OpenAiEmbedder
            | HuggingFaceEmbedder
            | OllamaEmbedder
            | RestEmbedder
            | UserProvidedEmbedder,
        ]
        | None
    ) = None  # Optional[Embedders] = None
