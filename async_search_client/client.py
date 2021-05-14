from __future__ import annotations

from types import TracebackType
from typing import Optional, Type

from httpx import AsyncClient

from async_search_client._http_requests import HttpRequests
from async_search_client.errors import MeiliSearchApiError
from async_search_client.index import Index
from async_search_client.models import ClientStats, DumpInfo, Health, IndexInfo, Keys, Version
from async_search_client.paths import Paths, build_url


class Client:
    def __init__(self, url: str, api_key: str = None, timeout: int = 5) -> None:
        self._http_client = AsyncClient(
            base_url=url, timeout=timeout, headers=self._set_headers(api_key)
        )
        self._http_requests = HttpRequests(self._http_client)

    async def __aenter__(self) -> Client:
        return self

    async def __aexit__(
        self,
        et: Optional[Type[BaseException]],
        ev: Optional[Type[BaseException]],
        traceback: Optional[TracebackType],
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """
        Closes the client. This only needs to be used if the client was not created with a context manager.
        """
        await self._http_client.aclose()

    async def create_dump(self) -> DumpInfo:
        response = await self._http_requests.post(build_url(Paths.DUMPS))
        return DumpInfo(**response.json())

    async def create_index(self, uid: str, primary_key: Optional[str] = None) -> Index:
        return await Index.create(self._http_client, uid, primary_key)

    async def get_indexes(self) -> Optional[list[Index]]:
        response = await self._http_requests.get(build_url(Paths.INDEXES))

        if not response.json():
            return None

        return [
            Index(
                http_client=self._http_client,
                uid=x["uid"],
                primary_key=x["primaryKey"],
                created_at=x["createdAt"],
                updated_at=x["updatedAt"],
            )
            for x in response.json()
        ]

    async def get_index(self, uid: str) -> Index:
        return await Index(self._http_client, uid).fetch_info()

    def index(self, uid: str) -> Index:
        """
        Create a local reference to an index identified by UID, without doing an HTTP call.
        Because no network call is made this method is not awaitable.
        """
        return Index(self._http_client, uid=uid)

    async def get_all_stats(self) -> ClientStats:
        response = await self._http_requests.get(build_url(Paths.STATS))
        return ClientStats(**response.json())

    async def get_dump_status(self, uid: str) -> DumpInfo:
        url = build_url(Paths.DUMPS, uid, "status")
        response = await self._http_requests.get(url)
        return DumpInfo(**response.json())

    async def get_or_create_index(self, uid: str, primary_key: Optional[str] = None) -> Index:
        try:
            index_instance = await self.get_index(uid)
        except MeiliSearchApiError as err:
            if "index_not_found" not in err.error_code:
                raise err
            index_instance = await self.create_index(uid, primary_key)
        return index_instance

    async def get_keys(self) -> Keys:
        response = await self._http_requests.get(build_url(Paths.KEYS))
        return Keys(**response.json())

    async def get_raw_index(self, uid: str) -> Optional[IndexInfo]:
        response = await self._http_client.get(build_url(Paths.INDEXES, uid))

        if response.status_code == 404:
            return None

        return IndexInfo(**response.json())

    async def get_raw_indexes(self) -> Optional[list[IndexInfo]]:
        response = await self._http_requests.get(build_url(Paths.INDEXES))

        if not response.json():
            return None

        return [IndexInfo(**x) for x in response.json()]

    async def get_version(self) -> Version:
        """
        Get version MeiliSearch that is running
        """
        response = await self._http_requests.get(build_url(Paths.VERSION))
        return Version(**response.json())

    async def health(self) -> Health:
        """
        Get health of the MeiliSearch server
        """
        response = await self._http_requests.get(build_url(Paths.HEALTH))
        return Health(**response.json())

    def _set_headers(self, api_key: str = None) -> dict[str, str]:
        if api_key:
            return {
                "X-Meili-Api-Key": api_key,
                "Content-Type": "application/json",
            }
        else:
            return {
                "Content-Type": "application/json",
            }
