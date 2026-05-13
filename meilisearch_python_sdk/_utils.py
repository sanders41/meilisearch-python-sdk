from __future__ import annotations

import sys
from functools import lru_cache
from typing import TYPE_CHECKING

from httpx2 import AsyncClient as HttpxAsyncClient
from httpx2 import Client as HttpxClient

if TYPE_CHECKING:
    from meilisearch_python_sdk._client import AsyncClient, Client  # pragma: no cover


def get_async_client(
    client: AsyncClient | HttpxAsyncClient,
) -> HttpxAsyncClient:
    if isinstance(client, HttpxAsyncClient):
        return client

    return client.http_client


def get_client(
    client: Client | HttpxClient,
) -> HttpxClient:
    if isinstance(client, HttpxClient):
        return client

    return client.http_client


@lru_cache(maxsize=1)
def use_task_groups() -> bool:
    return True if sys.version_info >= (3, 11) else False
