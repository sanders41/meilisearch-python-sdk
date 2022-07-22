from typing import Dict, List, Optional

from camel_converter.pydantic_base import CamelBase


class Overview(CamelBase):
    start: int
    length: int


class MatchesPosition(CamelBase):
    overview: List[Overview]


class SearchResults(CamelBase):
    hits: List[Dict]
    offset: int
    limit: int
    estimated_total_hits: int
    facets: Optional[Dict] = None
    processing_time_ms: float
    query: str
    _matches_position: Optional[MatchesPosition] = None
