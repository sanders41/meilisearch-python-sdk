from datetime import datetime
from typing import Dict, List, Optional

from camel_converter.pydantic_base import CamelBase

from meilisearch_python_async.models.index import IndexStats


class ClientStats(CamelBase):
    database_size: int
    last_update: Optional[datetime] = None
    indexes: Optional[Dict[str, IndexStats]] = None


class Key(CamelBase):
    description: str
    key: str
    actions: List[str]
    indexes: List[str]
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
