from __future__ import annotations

from types import TracebackType
from typing import Optional, Type

from httpx import AsyncClient

from async_search_client._http_requests import _HttpRequests
from async_search_client.errors import MeiliSearchApiError
from async_search_client.index import Index
from async_search_client.models import ClientStats, DumpInfo, Health, IndexInfo, Keys, Version


class Client:
    """The client to connect to the MeiliSearchApi."""

    def __init__(self, url: str, api_key: str = None, timeout: int = 5) -> None:
        """Class initializer.

        Args:
            url: The url to the MeiliSearch API (ex: http://localhost:7700)
            api_key: The optional API key for MeiliSearch. Defaults to None.
            timeout: The amount of time in seconds that the client will wait for a response before
                timing out. Defaults to 5.
        """
        self._http_client = AsyncClient(
            base_url=url, timeout=timeout, headers=self._set_headers(api_key)
        )
        self._http_requests = _HttpRequests(self._http_client)

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
        """Closes the client.

        This only needs to be used if the client was not created with context manager.
        """
        await self._http_client.aclose()

    async def create_dump(self) -> DumpInfo:
        """Trigger the creation of a MeiliSearch dump.

        Returns:
            Information about the dump.
            https://docs.meilisearch.com/reference/api/dump.html#create-a-dump

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        response = await self._http_requests.post("dumps")
        return DumpInfo(**response.json())

    async def create_index(self, uid: str, primary_key: Optional[str] = None) -> Index:
        """Creates a new index.

        Args:
            uid: The index's unique identifier.
            primary_key: The primary key of the documents. Defaults to None.

        Returns:
            An instance of Index containing the information of the newly created index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        return await Index.create(self._http_client, uid, primary_key)

    async def delete_index_if_exists(self, uid: str) -> bool:
        """Deletes an index if it already exists.

        Args:
            uid: The index's unique identifier.

        Returns:
            True if an index was deleted for False if not.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        try:
            url = f"indexes/{uid}"
            await self._http_requests.delete(url)
            return True
        except MeiliSearchApiError as error:
            if error.error_code != "index_not_found":
                raise error
            return False

    async def get_indexes(self) -> Optional[list[Index]]:
        """Get all indexes.

        Returns:
            A list of all indexes.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        response = await self._http_requests.get("indexes")

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
        """Gets a single index based on the uid of the index.

        Args:
            uid: The index's unique identifier.

        Returns:
            An Index instance containing the information of the fetched index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        return await Index(self._http_client, uid).fetch_info()

    def index(self, uid: str) -> Index:
        """Create a local reference to an index identified by UID, without making an HTTP call.

        Because no network call is made this method is not awaitable.

        Args:
            uid: The index's unique identifier.

        Returns:
            An Index instance.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        return Index(self._http_client, uid=uid)

    async def get_all_stats(self) -> ClientStats:
        """Get stats for all indexes.

        Returns:
            Information about database size and all indexes.
            https://docs.meilisearch.com/reference/api/stats.html

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        response = await self._http_requests.get("stats")
        return ClientStats(**response.json())

    async def get_dump_status(self, uid: str) -> DumpInfo:
        """Retrieve the status of a MeiliSearch dump creation.

        Args:
            uid: The index's unique identifier.

        Returns:
            Information about the dump status.
            https://docs.meilisearch.com/reference/api/dump.html#get-dump-status

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"dumps/{uid}/status"
        response = await self._http_requests.get(url)
        return DumpInfo(**response.json())

    async def get_or_create_index(self, uid: str, primary_key: Optional[str] = None) -> Index:
        """Get an index, or create it if it doesn't exist.

        Args:
            uid: The index's unique identifier.
            primary_key: The primary key of the documents. Defaults to None.

        Returns:
            An instance of Index containing the information of the retrieved or newly created index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.MeiliSearchTimeoutError: If the connection times out.
            MeiliSearchTimeoutError: If the connection times out.
        """
        try:
            index_instance = await self.get_index(uid)
        except MeiliSearchApiError as err:
            if "index_not_found" not in err.error_code:
                raise err
            index_instance = await self.create_index(uid, primary_key)
        return index_instance

    async def get_keys(self) -> Keys:
        """Gets the MeiliSearch public and private keys.

        Returns:
            The public and private keys.
            https://docs.meilisearch.com/reference/api/keys.html#get-keys

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        response = await self._http_requests.get("keys")
        return Keys(**response.json())

    async def get_raw_index(self, uid: str) -> Optional[IndexInfo]:
        """Gets the index and returns all the index information rather than an Index instance.

        Args:
            uid: The index's unique identifier.

        Returns:
            Index information rather than an Index instance.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        response = await self._http_client.get(f"indexes/{uid}")

        if response.status_code == 404:
            return None

        return IndexInfo(**response.json())

    async def get_raw_indexes(self) -> Optional[list[IndexInfo]]:
        """Gets all the indexes.

        Returns all the index information rather than an Index instance.

        Returns:
            A list of the Index information rather than an Index instances.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        response = await self._http_requests.get("indexes")

        if not response.json():
            return None

        return [IndexInfo(**x) for x in response.json()]

    async def get_version(self) -> Version:
        """Get the MeiliSearch version.

        Returns:
            Information about the version of MeiliSearch.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        response = await self._http_requests.get("version")
        return Version(**response.json())

    async def health(self) -> Health:
        """Get health of the MeiliSearch server.

        Returns:
            The status of the MeiliSearch server.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        response = await self._http_requests.get("health")
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
