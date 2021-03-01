from typing import Dict, List, Optional

from async_search_client.models.base_config import BaseConfig


class SearchResults(BaseConfig):
    hits: List[Dict]
    offset: int
    limit: int
    nb_hits: int
    exhaustive_nb_hits: bool
    facets_distribution: Optional[Dict] = None
    exhaustive_facets_count: Optional[bool] = None
    processing_time_ms: float
    query: str
