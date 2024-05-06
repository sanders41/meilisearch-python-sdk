from enum import Enum
from typing import Dict, List, Optional, Union
from warnings import warn

import pydantic
from camel_converter.pydantic_base import CamelBase

from meilisearch_python_sdk._utils import is_pydantic_2
from meilisearch_python_sdk.types import JsonDict


class MinWordSizeForTypos(CamelBase):
    one_typo: Optional[int] = None
    two_typos: Optional[int] = None


class TypoTolerance(CamelBase):
    enabled: bool = True
    disable_on_attributes: Optional[List[str]] = None
    disable_on_words: Optional[List[str]] = None
    min_word_size_for_typos: Optional[MinWordSizeForTypos] = None


class Faceting(CamelBase):
    max_values_per_facet: int
    sort_facet_values_by: Optional[Dict[str, str]] = None

    if is_pydantic_2():

        @pydantic.field_validator("sort_facet_values_by")  # type: ignore[attr-defined]
        @classmethod
        def validate_facet_order(cls, v: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
            if not v:  # pragma: no cover
                return None

            for _, value in v.items():
                if value not in ("alpha", "count"):
                    raise ValueError('facet_order must be either "alpha" or "count"')

            return v

    else:  # pragma: no cover
        warn(
            "The use of Pydantic less than version 2 is depreciated and will be removed in a future release",
            DeprecationWarning,
            stacklevel=2,
        )

        @pydantic.validator("sort_facet_values_by")  # type: ignore[attr-defined]
        @classmethod
        def validate_facet_order(cls, v: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
            if not v:
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
    model: Optional[str] = None  # Defaults to text-embedding-ada-002
    dimensions: Optional[int] = None  # Uses the model default
    api_key: Optional[str] = None  # Can be provided through a CLI option or environment variable
    document_template: Optional[str] = None
    distribution: Optional[Distribution] = None


class HuggingFaceEmbedder(CamelBase):
    source: str = "huggingFace"
    model: Optional[str] = None  # Defaults to BAAI/bge-base-en-v1.5
    revision: Optional[str] = None
    document_template: Optional[str] = None
    distribution: Optional[Distribution] = None


class OllamaEmbedder(CamelBase):
    source: str = "ollama"
    url: Optional[str] = None
    api_key: Optional[str] = None
    model: str
    document_template: Optional[str] = None
    distribution: Optional[Distribution] = None


class RestEmbedder(CamelBase):
    source: str = "rest"
    url: str
    api_key: Optional[str] = None
    dimensions: int
    document_template: Optional[str] = None
    input_field: Optional[List[str]] = None
    input_type: str = "text"
    query: JsonDict = {}
    path_to_embeddings: Optional[List[str]] = None
    embedding_object: Optional[List[str]] = None
    distribution: Optional[Distribution] = None


class UserProvidedEmbedder(CamelBase):
    source: str = "userProvided"
    dimensions: int
    distribution: Optional[Distribution] = None


class Embedders(CamelBase):
    embedders: Dict[
        str,
        Union[
            OpenAiEmbedder, HuggingFaceEmbedder, OllamaEmbedder, RestEmbedder, UserProvidedEmbedder
        ],
    ]


class ProximityPrecision(str, Enum):
    BY_WORD = "byWord"
    BY_ATTRIBUTE = "byAttribute"


class MeilisearchSettings(CamelBase):
    synonyms: Optional[JsonDict] = None
    stop_words: Optional[List[str]] = None
    ranking_rules: Optional[List[str]] = None
    filterable_attributes: Optional[List[str]] = None
    distinct_attribute: Optional[str] = None
    searchable_attributes: Optional[List[str]] = None
    displayed_attributes: Optional[List[str]] = None
    sortable_attributes: Optional[List[str]] = None
    typo_tolerance: Optional[TypoTolerance] = None
    faceting: Optional[Faceting] = None
    pagination: Optional[Pagination] = None
    proximity_precision: Optional[ProximityPrecision] = None
    separator_tokens: Optional[List[str]] = None
    non_separator_tokens: Optional[List[str]] = None
    search_cutoff_ms: Optional[int] = None
    dictionary: Optional[List[str]] = None
    embedders: Optional[
        Dict[
            str,
            Union[
                OpenAiEmbedder,
                HuggingFaceEmbedder,
                OllamaEmbedder,
                RestEmbedder,
                UserProvidedEmbedder,
            ],
        ]
    ] = None  # Optional[Embedders] = None
