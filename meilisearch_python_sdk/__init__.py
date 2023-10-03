from meilisearch_python_sdk._client import AsyncClient, Client
from meilisearch_python_sdk._index import AsyncIndex, Index
from meilisearch_python_sdk._version import VERSION

__version__ = VERSION


__all__ = ["AsyncClient", "AsyncIndex", "Client", "Index"]
