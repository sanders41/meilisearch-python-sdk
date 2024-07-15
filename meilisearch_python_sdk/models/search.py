from typing import List, Optional

import pydantic
from camel_converter.pydantic_base import CamelBase

from meilisearch_python_sdk.errors import MeilisearchError
from meilisearch_python_sdk.types import Filter, JsonDict


class FacetHits(CamelBase):
    value: str
    count: int


class FacetSearchResults(CamelBase):
    facet_hits: List[FacetHits]
    facet_query: str
    processing_time_ms: int


class Hybrid(CamelBase):
    semantic_ratio: float
    embedder: Optional[str] = None


class SearchParams(CamelBase):
    index_uid: str
    query: Optional[str] = pydantic.Field(None, alias="q")
    offset: int = 0
    limit: int = 20
    filter: Optional[Filter] = None
    facets: Optional[List[str]] = None
    attributes_to_retrieve: List[str] = ["*"]
    attributes_to_crop: Optional[List[str]] = None
    crop_length: int = 200
    attributes_to_highlight: Optional[List[str]] = None
    sort: Optional[List[str]] = None
    show_matches_position: bool = False
    highlight_pre_tag: str = "<em>"
    highlight_post_tag: str = "</em>"
    crop_marker: str = "..."
    matching_strategy: str = "all"
    hits_per_page: Optional[int] = None
    page: Optional[int] = None
    attributes_to_search_on: Optional[List[str]] = None
    show_ranking_score: bool = False
    show_ranking_score_details: bool = False
    ranking_score_threshold: Optional[float] = None
    vector: Optional[List[float]] = None
    hybrid: Optional[Hybrid] = None

    @pydantic.field_validator("ranking_score_threshold", mode="before")  # type: ignore[attr-defined]
    @classmethod
    def validate_ranking_score_threshold(cls, v: Optional[float]) -> Optional[float]:
        if v and not 0.0 <= v <= 1.0:
            raise MeilisearchError("ranking_score_threshold must be between 0.0 and 1.0")

        return v


class SearchResults(CamelBase):
    hits: List[JsonDict]
    offset: Optional[int] = None
    limit: Optional[int] = None
    estimated_total_hits: Optional[int] = None
    processing_time_ms: int
    query: str
    facet_distribution: Optional[JsonDict] = None
    total_pages: Optional[int] = None
    total_hits: Optional[int] = None
    page: Optional[int] = None
    hits_per_page: Optional[int] = None
    semantic_hit_count: Optional[int] = None


class SearchResultsWithUID(SearchResults):
    index_uid: str


class SimilarSearchResults(CamelBase):
    hits: List[JsonDict]
    id: str
    processing_time_ms: int
    limit: Optional[int] = None
    offset: Optional[int] = None
    estimated_total_hits: Optional[int] = None
