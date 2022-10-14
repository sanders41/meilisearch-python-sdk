from __future__ import annotations

import json
from datetime import datetime
from types import TracebackType
from typing import Any, Type

import jwt
from httpx import AsyncClient

from meilisearch_python_async._http_requests import HttpRequests
from meilisearch_python_async.errors import InvalidRestriction, MeiliSearchApiError
from meilisearch_python_async.index import Index
from meilisearch_python_async.models.client import ClientStats, Key, KeyCreate, KeySearch, KeyUpdate
from meilisearch_python_async.models.health import Health
from meilisearch_python_async.models.index import IndexInfo
from meilisearch_python_async.models.task import TaskInfo
from meilisearch_python_async.models.version import Version
from meilisearch_python_async.task import wait_for_task


class Client:
    """The client to connect to the MeiliSearchApi."""

    def __init__(self, url: str, api_key: str | None = None, *, timeout: int | None = None) -> None:
        """Class initializer.

        Args:

            url: The url to the MeiliSearch API (ex: http://localhost:7700)
            api_key: The optional API key for MeiliSearch. Defaults to None.
            timeout: The amount of time in seconds that the client will wait for a response before
                timing out. Defaults to None.
        """
        if api_key:
            headers = {"Authorization": f"Bearer {api_key}"}
        else:
            headers = None

        self.http_client = AsyncClient(base_url=url, timeout=timeout, headers=headers)
        self._http_requests = HttpRequests(self.http_client)

    async def __aenter__(self) -> Client:
        return self

    async def __aexit__(
        self,
        et: Type[BaseException] | None,
        ev: Type[BaseException] | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Closes the client.

        This only needs to be used if the client was not created with a context manager.
        """
        await self.http_client.aclose()

    async def create_dump(self) -> TaskInfo:
        """Trigger the creation of a MeiliSearch dump.

        Returns:

            The details of the task.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     await client.create_dump()
        """
        response = await self._http_requests.post("dumps")
        return TaskInfo(**response.json())

    async def create_index(self, uid: str, primary_key: str | None = None) -> Index:
        """Creates a new index.

        Args:

            uid: The index's unique identifier.
            primary_key: The primary key of the documents. Defaults to None.

        Returns:

            An instance of Index containing the information of the newly created index.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = await client.create_index("movies")
        """
        return await Index.create(self.http_client, uid, primary_key)

    async def delete_index_if_exists(self, uid: str) -> bool:
        """Deletes an index if it already exists.

        Args:

            uid: The index's unique identifier.

        Returns:

            True if an index was deleted for False if not.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     await client.delete_index_if_exists()
        """
        url = f"indexes/{uid}"
        response = await self._http_requests.delete(url)
        status = await wait_for_task(self.http_client, response.json()["taskUid"])
        if status.status == "succeeded":
            return True
        return False

    def generate_tenant_token(
        self,
        search_rules: dict[str, Any] | list[str],
        *,
        api_key: Key,
        expires_at: datetime | None = None,
    ) -> str:
        """Generates a JWT token to use for searching.

        Args:

            search_rules: Contains restrictions to use for the token. The default rules used for
                the API key used for signing can be used by setting searchRules to ["*"]. If "indexes"
                is included it must be equal to or more restrictive than the key used to generate the
                token.
            api_key: The API key to use to generate the token.
            expires_at: The timepoint at which the token should expire. If value is provided it
                shoud be a UTC time in the future. Default = None.

        Returns:

            A JWT token

        Raises:

            InvalidRestriction: If the restrictions are less strict than the permissions allowed
                in the API key.
            KeyNotFoundError: If no API search key is found.

        Examples:

            >>> from datetime import datetime, timedelta
            >>> from meilisearch_python_async import Client
            >>>
            >>> expires_at = datetime.utcnow() + timedelta(days=7)
            >>>
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     token = client.generate_tenant_token(
            >>>         search_rules = ["*"], api_key=api_key, expires_at=expires_at
            >>>     )
        """
        # if Client._valid_uuid(api_key.key) is False:
        #     raise Exception("The uid must comply to the uuid4 format.")

        if isinstance(search_rules, dict) and search_rules.get("indexes"):
            for index in search_rules["indexes"]:
                if api_key.indexes != ["*"] and index not in api_key.indexes:
                    raise InvalidRestriction(
                        "Invalid index. The token cannot be less restrictive than the API key"
                    )

        payload: dict[str, Any] = {"searchRules": search_rules}

        payload["apiKeyUid"] = api_key.uid
        if expires_at:
            if expires_at <= datetime.utcnow():
                raise ValueError("expires_at must be a time in the future")

            payload["exp"] = int(datetime.timestamp(expires_at))

        return jwt.encode(payload, api_key.key, algorithm="HS256")

    async def get_indexes(self) -> list[Index] | None:
        """Get all indexes.

        Returns:

            A list of all indexes.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     indexes = await client.get_indexes()
        """
        response = await self._http_requests.get("indexes")

        if not response.json()["results"]:
            return None

        return [
            Index(
                http_client=self.http_client,
                uid=x["uid"],
                primary_key=x["primaryKey"],
                created_at=x["createdAt"],
                updated_at=x["updatedAt"],
            )
            for x in response.json()["results"]
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

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = await client.get_index()
        """
        return await Index(self.http_client, uid).fetch_info()

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

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
        """
        return Index(self.http_client, uid=uid)

    async def get_all_stats(self) -> ClientStats:
        """Get stats for all indexes.

        Returns:

            Information about database size and all indexes.
            https://docs.meilisearch.com/reference/api/stats.html

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     stats = await client.get_all_stats()
        """
        response = await self._http_requests.get("stats")
        return ClientStats(**response.json())

    async def get_or_create_index(self, uid: str, primary_key: str | None = None) -> Index:
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

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = await client.get_or_create_index("movies")
        """
        try:
            index_instance = await self.get_index(uid)
        except MeiliSearchApiError as err:
            if "index_not_found" not in err.code:
                raise
            index_instance = await self.create_index(uid, primary_key)
        return index_instance

    async def create_key(self, key: KeyCreate) -> Key:
        """Creates a new API key.

        Args:

            key: The information to use in creating the key. Note that if an expires_at value
                is included it should be in UTC time.

        Returns:

            The new API key.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> from meilissearch_async_client.models.client import KeyCreate
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     key_info = KeyCreate(
            >>>         description="My new key",
            >>>         actions=["search"],
            >>>         indexes=["movies"],
            >>>     )
            >>>     keys = await client.create_key(key_info)
        """
        # The json.loads(key.json()) is because Pydantic can't serialize a date in a Python dict,
        # but can when converting to a json string.
        response = await self._http_requests.post("keys", json.loads(key.json(by_alias=True)))
        return Key(**response.json())

    async def delete_key(self, key: str) -> int:
        """Deletes an API key.

        Args:

            key: The key or uid to delete.

        Returns:

            The Response status code. 204 signifies a successful delete.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     await client.delete_key("abc123")
        """
        response = await self._http_requests.delete(f"keys/{key}")
        return response.status_code

    async def get_keys(self) -> KeySearch:
        """Gets the MeiliSearch API keys.

        Returns:

            API keys.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.

        Examples:

            from meilisearch_python_async import Client
            async with Client("http://localhost.com", "masterKey") as client:
                keys = await client.get_keys()
        """
        response = await self._http_requests.get("keys")
        return KeySearch(**response.json())

    async def get_key(self, key: str) -> Key:
        """Gets information about a specific API key.

        Args:

            key: The key for which to retrieve the information.

        Returns:

            The API key, or `None` if the key is not found.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     keys = await client.get_key("abc123")
        """
        response = await self._http_requests.get(f"keys/{key}")
        return Key(**response.json())

    async def update_key(self, key: KeyUpdate) -> Key:
        """Update an API key.

        Args:

            key: The information to use in updating the key. Note that if an expires_at value
                is included it should be in UTC time.

        Returns:

            The updated API key.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> from meilissearch_async_client.models.client import KeyUpdate
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     key_info = KeyUpdate(
                        key="abc123",
            >>>         indexes=["*"],
            >>>     )
            >>>     keys = await client.update_key(key_info)
        """
        # The json.loads(key.json()) is because Pydantic can't serialize a date in a Python dict,
        # but can when converting to a json string.
        payload = {k: v for k, v in json.loads(key.json(by_alias=True)).items() if v is not None}
        response = await self._http_requests.patch(f"keys/{key.key}", payload)
        return Key(**response.json())

    async def get_raw_index(self, uid: str) -> IndexInfo | None:
        """Gets the index and returns all the index information rather than an Index instance.

        Args:

            uid: The index's unique identifier.

        Returns:

            Index information rather than an Index instance.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = await client.get_raw_index("movies")
        """
        response = await self.http_client.get(f"indexes/{uid}")

        if response.status_code == 404:
            return None

        return IndexInfo(**response.json())

    async def get_raw_indexes(self) -> list[IndexInfo] | None:
        """Gets all the indexes.

        Returns all the index information rather than an Index instance.

        Returns:

            A list of the Index information rather than an Index instances.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = await client.get_raw_indexes()
        """
        response = await self._http_requests.get("indexes")

        if not response.json()["results"]:
            return None

        return [IndexInfo(**x) for x in response.json()["results"]]

    async def get_version(self) -> Version:
        """Get the MeiliSearch version.

        Returns:

            Information about the version of MeiliSearch.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     version = await client.get_version()
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

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     health = await client.get_healths()
        """
        response = await self._http_requests.get("health")
        return Health(**response.json())
