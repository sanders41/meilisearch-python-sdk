from typing import Any, Callable, Optional

from httpx import (
    AsyncClient,
    ConnectError,
    ConnectTimeout,
    HTTPError,
    RemoteProtocolError,
    Response,
)

from async_search_client.errors import MeiliSearchApiError, MeiliSearchCommunicationError


class HttpRequests:
    def __init__(self, http_client: AsyncClient) -> None:
        self.http_client = http_client

    async def _send_request(
        self,
        http_method: Callable,
        path: str,
        body: Optional[Any] = None,
    ) -> Response:
        try:
            if not body:
                response = await http_method(path)
            else:
                response = await http_method(path, json=body)

            response.raise_for_status()
            return response

        except RemoteProtocolError as err:
            raise MeiliSearchCommunicationError(str(err)) from err
        except ConnectError as err:
            raise MeiliSearchCommunicationError(str(err)) from err
        except ConnectTimeout as err:
            raise MeiliSearchCommunicationError(str(err)) from err
        except HTTPError as err:
            raise MeiliSearchApiError(str(err), response) from err

    async def get(self, path: str) -> Response:
        return await self._send_request(self.http_client.get, path)

    async def post(self, path: str, body: Optional[Any] = None) -> Response:
        return await self._send_request(self.http_client.post, path, body)

    async def put(self, path: str, body: Optional[Any] = None) -> Response:
        return await self._send_request(self.http_client.put, path, body)

    async def delete(self, path: str, body: Optional[dict] = None) -> Response:
        return await self._send_request(self.http_client.delete, path, body)
