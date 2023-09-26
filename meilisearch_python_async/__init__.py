from meilisearch_python_async._client import AsyncClient, Client
from meilisearch_python_async._index import AsyncIndex, Index
from meilisearch_python_async._version import VERSION

__version__ = VERSION


__all__ = ["AsyncClient", "AsyncIndex", "Client", "Index"]
