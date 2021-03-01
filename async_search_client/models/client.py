from datetime import datetime
from typing import Dict, Optional

from async_search_client.models.base_config import BaseConfig
from async_search_client.models.index import IndexStats


class ClientStats(BaseConfig):
    database_size: int
    last_update: Optional[datetime] = None
    indexes: Optional[Dict[str, IndexStats]] = None


class Keys(BaseConfig):
    public: Optional[str]
    private: Optional[str]
