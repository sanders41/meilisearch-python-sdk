from datetime import datetime
from typing import Dict, Optional

from async_search_client.models.base_config import BaseConfig


class IndexBase(BaseConfig):
    uid: str
    primary_key: Optional[str]


class IndexInfo(IndexBase):
    created_at: datetime
    updated_at: datetime


class IndexStats(BaseConfig):
    number_of_documents: int
    is_indexing: bool
    fields_distribution: Dict[str, int]
