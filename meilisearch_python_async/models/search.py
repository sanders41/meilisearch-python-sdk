from typing import Any, Dict, List, Optional

from camel_converter.pydantic_base import CamelBase


class SearchResults(CamelBase):
    hits: List[Dict[str, Any]]
    offset: int
    limit: int
    estimated_total_hits: int
    processing_time_ms: float
    query: str
    facet_distribution: Optional[Dict[str, Any]] = None
