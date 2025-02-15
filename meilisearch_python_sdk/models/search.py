from __future__ import annotations

from typing import Generic, Literal, TypeVar

from camel_converter.pydantic_base import CamelBase
from pydantic import Field, field_validator

from meilisearch_python_sdk.errors import MeilisearchError
from meilisearch_python_sdk.types import Filter, JsonDict

T = TypeVar("T")


class FacetHits(CamelBase):
    value: str
    count: int


class FacetSearchResults(CamelBase):
    facet_hits: list[FacetHits]
    facet_query: str | None
    processing_time_ms: int


class Hybrid(CamelBase):
    semantic_ratio: float
    embedder: str


class MergeFacets(CamelBase):
    max_values_per_facet: int


class Federation(CamelBase):
    limit: int = 20
    offset: int = 0
    facets_by_index: dict[str, list[str]] | None = None


class FederationMerged(CamelBase):
    limit: int = 20
    offset: int = 0
    facets_by_index: dict[str, list[str]] | None = None
    merge_facets: MergeFacets | None


class SearchParams(CamelBase):
    index_uid: str
    query: str | None = Field(None, alias="q")
    offset: int = 0
    limit: int = 20
    filter: Filter | None = None
    facets: list[str] | None = None
    attributes_to_retrieve: list[str] = ["*"]
    attributes_to_crop: list[str] | None = None
    crop_length: int = 200
    attributes_to_highlight: list[str] | None = None
    sort: list[str] | None = None
    show_matches_position: bool = False
    highlight_pre_tag: str = "<em>"
    highlight_post_tag: str = "</em>"
    crop_marker: str = "..."
    matching_strategy: Literal["all", "last", "frequency"] = "last"
    hits_per_page: int | None = None
    page: int | None = None
    attributes_to_search_on: list[str] | None = None
    show_ranking_score: bool = False
    show_ranking_score_details: bool = False
    ranking_score_threshold: float | None = None
    vector: list[float] | None = None
    hybrid: Hybrid | None = None
    locales: list[str] | None = None
    retrieve_vectors: bool | None = None

    @field_validator("ranking_score_threshold", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_ranking_score_threshold(cls, v: float | None) -> float | None:
        if v and not 0.0 <= v <= 1.0:
            raise MeilisearchError("ranking_score_threshold must be between 0.0 and 1.0")

        return v


class SearchResults(CamelBase, Generic[T]):
    hits: list[T]
    offset: int | None = None
    limit: int | None = None
    estimated_total_hits: int | None = None
    processing_time_ms: int
    query: str
    facet_distribution: JsonDict | None = None
    total_pages: int | None = None
    total_hits: int | None = None
    page: int | None = None
    hits_per_page: int | None = None
    semantic_hit_count: int | None = None


class SearchResultsWithUID(SearchResults, Generic[T]):
    index_uid: str


class SearchResultsFederated(CamelBase, Generic[T]):
    hits: list[T]
    offset: int | None = None
    limit: int | None = None
    estimated_total_hits: int | None = None
    processing_time_ms: int
    facet_distribution: JsonDict | None = None
    total_pages: int | None = None
    total_hits: int | None = None
    page: int | None = None
    hits_per_page: int | None = None
    semantic_hit_count: int | None = None
    facets_by_index: JsonDict | None = None


class SimilarSearchResults(CamelBase, Generic[T]):
    hits: list[T]
    id: str
    processing_time_ms: int
    limit: int | None = None
    offset: int | None = None
    estimated_total_hits: int | None = None
