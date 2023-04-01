from typing import Any, Dict, List, Optional, Union

from camel_converter.pydantic_base import CamelBase
from pydantic import Field


class SearchParams(CamelBase):
    index_uid: str
    query: Optional[str] = Field(None, alias="q")
    offset: int = 0
    limit: int = 20
    filter: Optional[Union[str, List[Union[str, List[str]]]]] = None
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


class SearchResults(CamelBase):
    hits: List[Dict[str, Any]]
    offset: Optional[int]
    limit: Optional[int]
    estimated_total_hits: Optional[int]
    processing_time_ms: int
    query: str
    facet_distribution: Optional[Dict[str, Any]] = None
    total_pages: Optional[int]
    total_hits: Optional[int]
    page: Optional[int]
    hits_per_page: Optional[int]


class SearchResultsWithUID(SearchResults):
    index_uid: str
