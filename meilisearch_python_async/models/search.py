from typing import Any, Dict, List, Optional

from camel_converter.pydantic_base import CamelBase


class SearchResults(CamelBase):
    hits: List[Dict[str, Any]]
    offset: Optional[int]
    limit: Optional[int]
    estimated_total_hits: Optional[int]
    processing_time_ms: float
    query: str
    facet_distribution: Optional[Dict[str, Any]] = None
    total_pages: Optional[int]
    total_hits: Optional[int]
    page: Optional[int]
    hits_per_page: Optional[int]
