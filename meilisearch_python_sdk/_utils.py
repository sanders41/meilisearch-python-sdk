from __future__ import annotations

import sys
from datetime import datetime
from functools import lru_cache
from typing import TYPE_CHECKING

from httpx import AsyncClient as HttpxAsyncClient
from httpx import Client as HttpxClient

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


def iso_to_date_time(iso_date: datetime | str | None) -> datetime | None:
    """Handle conversion of iso string to datetime.

    The microseconds from Meilisearch are sometimes too long for python to convert so this
    strips off the last digits to shorten it when that happens.
    """
    if not iso_date:
        return None

    if isinstance(iso_date, datetime):
        return iso_date

    try:
        return datetime.strptime(iso_date, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        split = iso_date.split(".")
        if len(split) < 2:
            raise
        reduce = len(split[1]) - 6
        reduced = f"{split[0]}.{split[1][:-reduce]}Z"
        return datetime.strptime(reduced, "%Y-%m-%dT%H:%M:%S.%fZ")


@lru_cache(maxsize=1)
def use_task_groups() -> bool:
    return True if sys.version_info >= (3, 11) else False
