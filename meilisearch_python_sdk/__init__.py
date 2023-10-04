from meilisearch_python_sdk._client import AsyncClient, Client
from meilisearch_python_sdk._version import VERSION
from meilisearch_python_sdk.index import AsyncIndex, Index

__version__ = VERSION


__all__ = ["AsyncClient", "AsyncIndex", "Client", "Index"]
