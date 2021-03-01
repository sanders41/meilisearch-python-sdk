from typing import Any, Dict, List, Optional

from async_search_client.models.base_config import BaseConfig


class MeiliSearchSettings(BaseConfig):
    synonyms: Optional[Dict[str, Any]] = None
    stop_words: Optional[List[str]] = None
    ranking_rules: Optional[List[str]] = None
    attributes_for_faceting: Optional[List[str]] = None
    distinct_attribute: Optional[str] = None
    searchable_attributes: Optional[List[str]] = None
    displayed_attributes: Optional[List[str]] = None
