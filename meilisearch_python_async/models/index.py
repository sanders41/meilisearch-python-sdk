from datetime import datetime
from typing import Dict, Optional

from camel_converter.pydantic_base import CamelBase


class IndexBase(CamelBase):
    uid: str
    primary_key: Optional[str]


class IndexInfo(IndexBase):
    created_at: datetime
    updated_at: datetime


class IndexStats(CamelBase):
    number_of_documents: int
    is_indexing: bool
    field_distribution: Dict[str, int]
