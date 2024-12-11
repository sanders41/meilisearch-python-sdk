from __future__ import annotations

import gzip
from functools import lru_cache
from typing import Any, Callable

from httpx import (
    AsyncClient,
    Client,
    ConnectError,
    ConnectTimeout,
    HTTPError,
    RemoteProtocolError,
    Response,
)

from meilisearch_python_sdk._version import VERSION
from meilisearch_python_sdk.errors import (
    MeilisearchApiError,
    MeilisearchCommunicationError,
    MeilisearchError,
)
from meilisearch_python_sdk.json_handler import BuiltinHandler, OrjsonHandler, UjsonHandler


class AsyncHttpRequests:
    def __init__(
        self, http_client: AsyncClient, json_handler: BuiltinHandler | OrjsonHandler | UjsonHandler
    ) -> None:
        self.http_client = http_client
        self.json_handler = json_handler

    async def _send_request(
        self,
        http_method: Callable,
        path: str,
        body: Any | None = None,
        content_type: str = "application/json",
        compress: bool = False,
    ) -> Response:
        headers = build_headers(content_type, compress)

        try:
            if body is None:
                response = await http_method(path)
            elif content_type == "application/json" and not compress:
                response = await http_method(
                    path, content=self.json_handler.dumps(body), headers=headers
                )
            else:
                if body and compress:
                    if content_type == "application/json":
                        body = gzip.compress(self.json_handler.dumps(body).encode("utf-8"))
                    else:
                        body = gzip.compress((body).encode("utf-8"))
                response = await http_method(path, content=body, headers=headers)

            response.raise_for_status()
            return response

        except (ConnectError, ConnectTimeout, RemoteProtocolError) as err:
            raise MeilisearchCommunicationError(str(err)) from err
        except HTTPError as err:
            if "response" in locals():
                if "application/json" in response.headers.get("content-type", ""):
                    raise MeilisearchApiError(str(err), response) from err
                else:
                    raise
            else:
                # Fail safe just in case error happens before response is created
                raise MeilisearchError(str(err)) from err  # pragma: no cover

    async def get(self, path: str) -> Response:
        return await self._send_request(self.http_client.get, path)

    async def patch(
        self,
        path: str,
        body: Any | None = None,
        content_type: str = "application/json",
        compress: bool = False,
    ) -> Response:
        return await self._send_request(self.http_client.patch, path, body, content_type, compress)

    async def post(
        self,
        path: str,
        body: Any | None = None,
        content_type: str = "application/json",
        compress: bool = False,
    ) -> Response:
        return await self._send_request(self.http_client.post, path, body, content_type, compress)

    async def put(
        self,
        path: str,
        body: Any | None = None,
        content_type: str = "application/json",
        compress: bool = False,
    ) -> Response:
        return await self._send_request(self.http_client.put, path, body, content_type, compress)

    async def delete(self, path: str, body: dict | None = None) -> Response:
        return await self._send_request(self.http_client.delete, path, body)


class HttpRequests:
    def __init__(
        self, http_client: Client, json_handler: BuiltinHandler | OrjsonHandler | UjsonHandler
    ) -> None:
        self.http_client = http_client
        self.json_handler = json_handler

    def _send_request(
        self,
        http_method: Callable,
        path: str,
        body: Any | None = None,
        content_type: str = "application/json",
        compress: bool = False,
    ) -> Response:
        headers = build_headers(content_type, compress)
        try:
            if body is None:
                response = http_method(path)
            elif content_type == "application/json" and not compress:
                response = http_method(path, content=self.json_handler.dumps(body), headers=headers)
            else:
                if body and compress:
                    if content_type == "application/json":
                        body = gzip.compress(self.json_handler.dumps(body).encode("utf-8"))
                    else:
                        body = gzip.compress((body).encode("utf-8"))
                response = http_method(path, content=body, headers=headers)

            response.raise_for_status()
            return response

        except (ConnectError, ConnectTimeout, RemoteProtocolError) as err:
            raise MeilisearchCommunicationError(str(err)) from err
        except HTTPError as err:
            if "response" in locals():
                if "application/json" in response.headers.get("content-type", ""):
                    raise MeilisearchApiError(str(err), response) from err
                else:
                    raise
            else:
                # Fail safe just in case error happens before response is created
                raise MeilisearchError(str(err)) from err  # pragma: no cover

    def get(self, path: str) -> Response:
        return self._send_request(self.http_client.get, path)

    def patch(
        self,
        path: str,
        body: Any | None = None,
        content_type: str = "application/json",
        compress: bool = False,
    ) -> Response:
        return self._send_request(self.http_client.patch, path, body, content_type, compress)

    def post(
        self,
        path: str,
        body: Any | None = None,
        content_type: str = "application/json",
        compress: bool = False,
    ) -> Response:
        return self._send_request(self.http_client.post, path, body, content_type, compress)

    def put(
        self,
        path: str,
        body: Any | None = None,
        content_type: str = "application/json",
        compress: bool = False,
    ) -> Response:
        return self._send_request(self.http_client.put, path, body, content_type, compress)

    def delete(self, path: str, body: dict | None = None) -> Response:
        return self._send_request(self.http_client.delete, path, body)


def build_headers(content_type: str, compress: bool) -> dict[str, str]:
    headers = {"user-agent": user_agent(), "Content-Type": content_type}

    if compress:
        headers["Content-Encoding"] = "gzip"

    return headers


@lru_cache(maxsize=1)
def user_agent() -> str:
    return f"Meilisearch Python SDK (v{VERSION})"
