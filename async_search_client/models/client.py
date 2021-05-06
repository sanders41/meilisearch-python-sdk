from datetime import datetime
from typing import Dict, Optional

from camel_converter.pydantic_base import CamelBase

from async_search_client.models.index import IndexStats


class ClientStats(CamelBase):
    database_size: int
    last_update: Optional[datetime] = None
    indexes: Optional[Dict[str, IndexStats]] = None


class Keys(CamelBase):
    public: Optional[str]
    private: Optional[str]
