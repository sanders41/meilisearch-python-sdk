from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable

from httpx import (
    AsyncClient,
    ConnectError,
    ConnectTimeout,
    HTTPError,
    RemoteProtocolError,
    Response,
)

from meilisearch_python_async._version import VERSION
from meilisearch_python_async.errors import (
    MeilisearchApiError,
    MeilisearchCommunicationError,
    MeilisearchError,
)


class HttpRequests:
    def __init__(self, http_client: AsyncClient) -> None:
        self.http_client = http_client

    async def _send_request(
        self,
        http_method: Callable,
        path: str,
        body: Any | None = None,
        content_type: str = "applicaton/json",
    ) -> Response:
        headers = {"user-agent": user_agent()}
        try:
            if not body:
                response = await http_method(path)
            elif content_type != "application/json":
                headers["Content-Type"] = content_type
                response = await http_method(path, content=body, headers=headers)
            else:
                headers["Content-Type"] = content_type
                response = await http_method(path, json=body, headers=headers)

            response.raise_for_status()
            return response

        except (ConnectError, ConnectTimeout, RemoteProtocolError) as err:
            raise MeilisearchCommunicationError(str(err)) from err
        except HTTPError as err:
            if "response" in locals():
                raise MeilisearchApiError(str(err), response) from err
            else:
                # Fail safe just in case error happens before response is created
                raise MeilisearchError(str(err))  # pragma: no cover

    async def get(self, path: str) -> Response:
        return await self._send_request(self.http_client.get, path)

    async def patch(
        self, path: str, body: Any | None = None, content_type: str = "application/json"
    ) -> Response:
        return await self._send_request(self.http_client.patch, path, body, content_type)

    async def post(
        self, path: str, body: Any | None = None, content_type: str = "application/json"
    ) -> Response:
        return await self._send_request(self.http_client.post, path, body, content_type)

    async def put(
        self, path: str, body: Any | None = None, content_type: str = "application/json"
    ) -> Response:
        return await self._send_request(self.http_client.put, path, body, content_type)

    async def delete(self, path: str, body: dict | None = None) -> Response:
        return await self._send_request(self.http_client.delete, path, body)


@lru_cache(maxsize=1)
def user_agent() -> str:
    return f"Meilisearch Python Async (v{VERSION})"
