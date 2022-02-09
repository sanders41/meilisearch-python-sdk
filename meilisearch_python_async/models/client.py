from datetime import datetime
from typing import Dict, List, Optional

from camel_converter.pydantic_base import CamelBase

from meilisearch_python_async.models.index import IndexStats


class ClientStats(CamelBase):
    database_size: int
    last_update: Optional[datetime] = None
    indexes: Optional[Dict[str, IndexStats]] = None


class _KeyBase(CamelBase):
    description: str
    actions: List[str]
    indexes: List[str]
    expires_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: None if not v else f"{str(v).split('.')[0].replace(' ', 'T')}Z"
        }


class Key(_KeyBase):
    key: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class KeyCreate(_KeyBase):
    pass


class KeyUpdate(_KeyBase):
    key: str
