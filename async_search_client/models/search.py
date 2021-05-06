from typing import Dict, List, Optional

from camel_converter.pydantic_base import CamelBase


class SearchResults(CamelBase):
    hits: List[Dict]
    offset: int
    limit: int
    nb_hits: int
    exhaustive_nb_hits: bool
    facets_distribution: Optional[Dict] = None
    exhaustive_facets_count: Optional[bool] = None
    processing_time_ms: float
    query: str
