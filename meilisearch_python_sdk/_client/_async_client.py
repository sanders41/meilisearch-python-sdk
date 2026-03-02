from __future__ import annotations

from datetime import datetime
from ssl import SSLContext
from typing import TYPE_CHECKING, Any

from camel_converter import dict_to_camel
from httpx import AsyncClient as HttpxAsyncClient

from meilisearch_python_sdk import _task
from meilisearch_python_sdk._batch import async_get_batch, async_get_batches
from meilisearch_python_sdk._client._base_client import BaseClient
from meilisearch_python_sdk._client._common import (
    build_multi_search_payload,
    build_offset_limit_url,
    build_swap_indexes_payload,
    build_transfer_documents_payload,
    build_update_key_payload,
)
from meilisearch_python_sdk._http_requests import AsyncHttpRequests
from meilisearch_python_sdk.errors import MeilisearchApiError
from meilisearch_python_sdk.index import AsyncIndex
from meilisearch_python_sdk.json_handler import BuiltinHandler, OrjsonHandler
from meilisearch_python_sdk.models.client import (
    ClientStats,
    Key,
    KeyCreate,
    KeySearch,
    KeyUpdate,
    Network,
)
from meilisearch_python_sdk.models.health import Health
from meilisearch_python_sdk.models.index import IndexInfo
from meilisearch_python_sdk.models.search import (
    Federation,
    FederationMerged,
    SearchParams,
    SearchResultsFederated,
    SearchResultsWithUID,
)
from meilisearch_python_sdk.models.settings import MeilisearchSettings
from meilisearch_python_sdk.models.task import TaskInfo, TaskResult, TaskStatus
from meilisearch_python_sdk.models.version import Version
from meilisearch_python_sdk.models.webhook import Webhook, WebhookCreate, Webhooks, WebhookUpdate
from meilisearch_python_sdk.plugins import AsyncIndexPlugins
from meilisearch_python_sdk.types import JsonDict

if TYPE_CHECKING:
    import sys
    from types import TracebackType

    from meilisearch_python_sdk.models.batch import BatchResult, BatchStatus
    from meilisearch_python_sdk.types import JsonMapping

    if sys.version_info >= (3, 11):
        from typing import Self
    else:
        from typing_extensions import Self


class AsyncClient(BaseClient):
    """Async client to connect to the Meilisearch API."""

    def __init__(
        self,
        url: str,
        api_key: str | None = None,
        *,
        timeout: int | None = None,
        verify: bool | SSLContext = True,
        custom_headers: dict[str, str] | None = None,
        json_handler: BuiltinHandler | OrjsonHandler | None = None,
        http2: bool = False,
    ) -> None:
        """Class initializer.

        Args:
            url: The url to the Meilisearch API (ex: http://localhost:7700)
            api_key: The optional API key for Meilisearch. Defaults to None.
            timeout: The amount of time in seconds that the client will wait for a response before
                timing out. Defaults to None.
            verify: SSL certificates (a.k.a CA bundle) used to
                verify the identity of requested hosts. Either `True` (default CA bundle),
                a path to an SSL certificate file, or `False` (disable verification)
            custom_headers: Custom headers to add when sending data to Meilisearch. Defaults to
                None.
            json_handler: The module to use for json operations. The options are BuiltinHandler
                (uses the json module from the standard library), or OrjsonHandler (uses orjson).
                Note that in order use orjson the corresponding extra needs to be included.
                Default: BuiltinHandler.
            http2: Whether or not to use HTTP/2. Defaults to False.
        """
        super().__init__(api_key, custom_headers, json_handler)

        self.http_client = HttpxAsyncClient(
            base_url=url, timeout=timeout, headers=self._headers, verify=verify, http2=http2
        )
        self._http_requests = AsyncHttpRequests(self.http_client, json_handler=self.json_handler)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        et: type[BaseException] | None,
        ev: type[BaseException] | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Closes the client.

        This only needs to be used if the client was not created with a context manager.
        """
        await self.http_client.aclose()

    async def add_or_update_networks(self, *, network: Network) -> Network:
        """Set or update remote networks.

        Args:
            network: Information to use for the networks.

        Returns:
            An instance of Network containing the network information.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:
            >>> from meilisearch_python_sdk import AsyncClient
            >>> from meilisearch_python_sdk.models.client import Network, Remote
            >>>
            >>>
            >>> network = Network(
            >>> self_="remote_1",
            >>>     remotes={
            >>>         "remote_1": {"url": "http://localhost:7700", "searchApiKey": "xxxx"},
            >>>         "remote_2": {"url": "http://localhost:7720", "searchApiKey": "xxxx"},
            >>>     },
            >>> )
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     response = await client.add_or_update_networks(network=network)
        """
        response = await self._http_requests.patch(
            "network", network.model_dump(by_alias=True, exclude_none=True)
        )

        return Network(**self._http_requests.parse_json(response))

    async def get_networks(self) -> Network:
        """Fetches the remote-networks

        Returns:
            An instance of Network containing information about each remote.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:
            >>> from meilisearch_python_sdk import AsyncClient
            >>>
            >>>
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     response = await client.get_networks()
        """
        response = await self._http_requests.get("network")

        return Network(**self._http_requests.parse_json(response))

    async def get_webhooks(self) -> Webhooks:
        """Get all webhooks.

        Returns:
            An instance of Webhooks containing all configured webhooks.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     webhooks = await client.get_webhooks()
        """
        response = await self._http_requests.get("webhooks")

        return Webhooks(**self._http_requests.parse_json(response))

    async def get_webhook(self, uuid: str) -> Webhook:
        """Get a specific webhook by UUID.

        Args:
            uuid: The webhook's unique identifier.

        Returns:
            An instance of Webhook containing the webhook information.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     webhook = await client.get_webhook("abc-123")
        """
        response = await self._http_requests.get(f"webhooks/{uuid}")

        return Webhook(**self._http_requests.parse_json(response))

    async def create_webhook(self, webhook: WebhookCreate) -> Webhook:
        """Create a new webhook.

        Args:
            webhook: The webhook configuration to create.

        Returns:
            The created webhook.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:
            >>> from meilisearch_python_sdk import AsyncClient
            >>> from meilisearch_python_sdk.models.webhook import WebhookCreate
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     webhook_config = WebhookCreate(
            >>>         url="https://example.com/webhook",
            >>>         headers={"Authorization": "Bearer token"}
            >>>     )
            >>>     webhook = await client.create_webhook(webhook_config)
        """
        response = await self._http_requests.post(
            "webhooks", webhook.model_dump(by_alias=True, exclude_none=True)
        )

        return Webhook(**self._http_requests.parse_json(response))

    async def update_webhook(self, *, uuid: str, webhook: WebhookUpdate) -> Webhook:
        """Update an existing webhook.

        Args:
            uuid: The webhook's unique identifier.
            webhook: The webhook configuration updates.

        Returns:
            The updated webhook.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:
            >>> from meilisearch_python_sdk import AsyncClient
            >>> from meilisearch_python_sdk.models.webhook import WebhookUpdate
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     webhook_update = WebhookUpdate(url="https://example.com/new-webhook")
            >>>     webhook = await client.update_webhook("abc-123", webhook_update)
        """
        response = await self._http_requests.patch(
            f"webhooks/{uuid}", webhook.model_dump(by_alias=True, exclude_none=True)
        )

        return Webhook(**self._http_requests.parse_json(response))

    async def delete_webhook(self, uuid: str) -> int:
        """Delete a webhook.

        Args:
            uuid: The webhook's unique identifier.

        Returns:
            The Response status code. 204 signifies a successful delete.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     await client.delete_webhook("abc-123")
        """
        response = await self._http_requests.delete(f"webhooks/{uuid}")
        return response.status_code

    async def create_dump(self) -> TaskInfo:
        """Trigger the creation of a Meilisearch dump.

        Returns:
            The details of the task.
        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     await client.create_dump()
        """
        response = await self._http_requests.post("dumps")

        return TaskInfo(**self._http_requests.parse_json(response))

    async def create_index(
        self,
        uid: str,
        primary_key: str | None = None,
        *,
        settings: MeilisearchSettings | None = None,
        wait: bool = True,
        timeout_in_ms: int | None = None,
        plugins: AsyncIndexPlugins | None = None,
        hits_type: Any = JsonDict,  # noqa: ANN401
    ) -> AsyncIndex:
        """Creates a new index.

        Args:
            uid: The index's unique identifier.
            primary_key: The primary key of the documents. Defaults to None.
            settings: Settings for the index. The settings can also be updated independently of
                creating the index. The advantage to updating them here is updating the settings after
                adding documents will cause the documents to be re-indexed. Because of this it will be
                faster to update them before adding documents. Defaults to None (i.e. default
                Meilisearch index settings).
            wait: If set to True and settings are being updated, the index will be returned after
                the settings update has completed. If False it will not wait for settings to complete.
                Default: True
            timeout_in_ms: Amount of time in milliseconds to wait before raising a
                MeilisearchTimeoutError. `None` can also be passed to wait indefinitely. Be aware that
                if the `None` option is used the wait time could be very long. Defaults to None.
            plugins: Optional plugins can be provided to extend functionality.
            hits_type: Allows for a custom type to be passed to use for hits. Defaults to
                JsonDict

        Returns:
            An instance of AsyncIndex containing the information of the newly created index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = await client.create_index("movies")
        """
        return await AsyncIndex.create(
            self.http_client,
            uid,
            primary_key,
            settings=settings,
            wait=wait,
            timeout_in_ms=timeout_in_ms,
            plugins=plugins,
            json_handler=self.json_handler,
            hits_type=hits_type,
        )

    async def create_snapshot(self) -> TaskInfo:
        """Trigger the creation of a Meilisearch snapshot.

        Returns:
            The details of the task.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     await client.create_snapshot()
        """
        response = await self._http_requests.post("snapshots")

        return TaskInfo(**self._http_requests.parse_json(response))

    async def delete_index_if_exists(self, uid: str) -> bool:
        """Deletes an index if it already exists.

        Args:
            uid: The index's unique identifier.

        Returns:
            True if an index was deleted for False if not.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     await client.delete_index_if_exists()
        """
        response = await self._http_requests.delete(f"indexes/{uid}")
        status = await self.wait_for_task(
            self._http_requests.parse_json(response)["taskUid"], timeout_in_ms=100000
        )
        if status.status == "succeeded":
            return True
        return False

    async def get_indexes(
        self, *, offset: int | None = None, limit: int | None = None
    ) -> list[AsyncIndex] | None:
        """Get all indexes.

        Args:
            offset: Number of indexes to skip. The default of None will use the Meilisearch
                default.
            limit: Number of indexes to return. The default of None will use the Meilisearch
                default.

        Returns:
            A list of all indexes.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     indexes = await client.get_indexes()
        """
        url = build_offset_limit_url("indexes", offset, limit)
        response = await self._http_requests.get(url)
        parsed = self._http_requests.parse_json(response)

        if not parsed["results"]:
            return None

        return [
            AsyncIndex(
                http_client=self.http_client,
                uid=x["uid"],
                primary_key=x["primaryKey"],
                created_at=x["createdAt"],
                updated_at=x["updatedAt"],
                json_handler=self.json_handler,
            )
            for x in parsed["results"]
        ]

    async def get_index(self, uid: str) -> AsyncIndex:
        """Gets a single index based on the uid of the index.

        Args:
            uid: The index's unique identifier.

        Returns:
            An AsyncIndex instance containing the information of the fetched index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = await client.get_index()
        """
        return await AsyncIndex(self.http_client, uid, json_handler=self.json_handler).fetch_info()

    def index(self, uid: str, *, plugins: AsyncIndexPlugins | None = None) -> AsyncIndex:
        """Create a local reference to an index identified by UID, without making an HTTP call.

        Because no network call is made this method is not awaitable.

        Args:
            uid: The index's unique identifier.
            plugins: Optional plugins can be provided to extend functionality.

        Returns:
            An AsyncIndex instance.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
        """
        return AsyncIndex(
            self.http_client, uid=uid, plugins=plugins, json_handler=self.json_handler
        )

    async def get_all_stats(self) -> ClientStats:
        """Get stats for all indexes.

        Returns:
            Information about database size and all indexes.
            https://docs.meilisearch.com/reference/api/stats.html

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     stats = await client.get_all_stats()
        """
        response = await self._http_requests.get("stats")

        return ClientStats(**self._http_requests.parse_json(response))

    async def get_or_create_index(
        self,
        uid: str,
        primary_key: str | None = None,
        *,
        plugins: AsyncIndexPlugins | None = None,
        hits_type: Any = JsonDict,  # noqa: ANN401
    ) -> AsyncIndex:
        """Get an index, or create it if it doesn't exist.

        Args:
            uid: The index's unique identifier.
            primary_key: The primary key of the documents. Defaults to None.
            plugins: Optional plugins can be provided to extend functionality.
            hits_type: Allows for a custom type to be passed to use for hits. Defaults to
                JsonDict

        Returns:
            An instance of AsyncIndex containing the information of the retrieved or newly created index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.MeilisearchTimeoutError: If the connection times out.
            MeilisearchTimeoutError: If the connection times out.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = await client.get_or_create_index("movies")
        """
        try:
            index_instance = await self.get_index(uid)
        except MeilisearchApiError as err:
            if "index_not_found" not in err.code:
                raise
            index_instance = await self.create_index(
                uid, primary_key, plugins=plugins, hits_type=hits_type
            )
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
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> from meilissearch_async_client.models.client import KeyCreate
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     key_info = KeyCreate(
            >>>         description="My new key",
            >>>         actions=["search"],
            >>>         indexes=["movies"],
            >>>     )
            >>>     keys = await client.create_key(key_info)
        """
        response = await self._http_requests.post(
            "keys", key.model_dump(by_alias=True, mode="json")
        )

        return Key(**self._http_requests.parse_json(response))

    async def delete_key(self, key: str) -> int:
        """Deletes an API key.

        Args:
            key: The key or uid to delete.

        Returns:
            The Response status code. 204 signifies a successful delete.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     await client.delete_key("abc123")
        """
        response = await self._http_requests.delete(f"keys/{key}")
        return response.status_code

    async def get_keys(self, *, offset: int | None = None, limit: int | None = None) -> KeySearch:
        """Gets the Meilisearch API keys.

        Args:
            offset: Number of indexes to skip. The default of None will use the Meilisearch
                default.
            limit: Number of indexes to return. The default of None will use the Meilisearch
                default.

        Returns:
            API keys.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            from meilisearch_python_sdk import AsyncClient
            async with AsyncClient("http://localhost.com", "masterKey") as client:
                keys = await client.get_keys()
        """
        url = build_offset_limit_url("keys", offset, limit)
        response = await self._http_requests.get(url)

        return KeySearch(**self._http_requests.parse_json(response))

    async def get_key(self, key: str) -> Key:
        """Gets information about a specific API key.

        Args:
            key: The key for which to retrieve the information.

        Returns:
            The API key, or `None` if the key is not found.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     keys = await client.get_key("abc123")
        """
        response = await self._http_requests.get(f"keys/{key}")

        return Key(**self._http_requests.parse_json(response))

    async def update_key(self, key: KeyUpdate) -> Key:
        """Update an API key.

        Args:
            key: The information to use in updating the key. Note that if an expires_at value
                is included it should be in UTC time.

        Returns:
            The updated API key.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> from meilissearch_async_client.models.client import KeyUpdate
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     key_info = KeyUpdate(
                        key="abc123",
            >>>         indexes=["*"],
            >>>     )
            >>>     keys = await client.update_key(key_info)
        """
        payload = build_update_key_payload(key, self.json_handler)
        response = await self._http_requests.patch(f"keys/{key.key}", payload)

        return Key(**self._http_requests.parse_json(response))

    async def multi_search(
        self,
        queries: list[SearchParams],
        *,
        federation: Federation | FederationMerged | None = None,
        hits_type: Any = JsonDict,  # noqa: ANN401
    ) -> list[SearchResultsWithUID] | SearchResultsFederated:
        """Multi-index search.

        Args:
            queries: List of SearchParameters
            federation: If included a single search result with hits built from all queries will
                be returned. This parameter can only be used with Meilisearch >= v1.10.0. Defaults
                to None.
            hits_type: Allows for a custom type to be passed to use for hits. Defaults to
                JsonDict

        Returns:
            Results of the search

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> from meilisearch_python_sdk.models.search import SearchParams
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     queries = [
            >>>         SearchParams(index_uid="my_first_index", query"Some search"),
            >>>         SearchParams(index_uid="my_second_index", query="Another search")
            >>>     ]
            >>>     search_results = await client.search(queries)
        """
        url = "multi-search"
        processed_queries, federation_payload = build_multi_search_payload(queries, federation)

        response = await self._http_requests.post(
            url,
            body={
                "federation": federation_payload,
                "queries": processed_queries,
            },
        )

        if federation:
            results = self._http_requests.parse_json(response)
            return SearchResultsFederated[hits_type](**results)

        return [
            SearchResultsWithUID[hits_type](**x)
            for x in self._http_requests.parse_json(response)["results"]
        ]

    async def get_raw_index(self, uid: str) -> IndexInfo | None:
        """Gets the index and returns all the index information rather than an AsyncIndex instance.

        Args:
            uid: The index's unique identifier.

        Returns:
            Index information rather than an AsyncIndex instance.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = await client.get_raw_index("movies")
        """
        response = await self.http_client.get(f"indexes/{uid}")

        if response.status_code == 404:
            return None

        return IndexInfo(**self._http_requests.parse_json(response))

    async def get_raw_indexes(
        self, *, offset: int | None = None, limit: int | None = None
    ) -> list[IndexInfo] | None:
        """Gets all the indexes.

        Args:
            offset: Number of indexes to skip. The default of None will use the Meilisearch
                default.
            limit: Number of indexes to return. The default of None will use the Meilisearch
                default.

        Returns all the index information rather than an AsyncIndex instance.

        Returns:
            A list of the Index information rather than an AsyncIndex instances.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = await client.get_raw_indexes()
        """
        url = build_offset_limit_url("indexes", offset, limit)
        response = await self._http_requests.get(url)
        parsed = self._http_requests.parse_json(response)

        if not parsed["results"]:
            return None

        return [IndexInfo(**x) for x in parsed["results"]]

    async def get_version(self) -> Version:
        """Get the Meilisearch version.

        Returns:
            Information about the version of Meilisearch.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     version = await client.get_version()
        """
        response = await self._http_requests.get("version")

        return Version(**self._http_requests.parse_json(response))

    async def health(self) -> Health:
        """Get health of the Meilisearch server.

        Returns:
            The status of the Meilisearch server.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     health = await client.get_health()
        """
        response = await self._http_requests.get("health")

        return Health(**self._http_requests.parse_json(response))

    async def swap_indexes(self, indexes: list[tuple[str, str]], rename: bool = False) -> TaskInfo:
        """Swap two indexes.

        Args:
            indexes: A list of tuples, each tuple should contain the indexes to swap.
            rename: Use rename false if you are swapping two existing indexes. Use rename true if
                the second index in your array does not exist. Default = False

        Returns:
            The details of the task.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = await client.swap_indexes([("index_a", "index_b")])
        """
        processed_indexes = build_swap_indexes_payload(indexes, rename)
        response = await self._http_requests.post("swap-indexes", processed_indexes)

        return TaskInfo(**self._http_requests.parse_json(response))

    async def get_batch(self, batch_uid: int) -> BatchResult | None:
        return await async_get_batch(self, batch_uid)

    async def get_batches(
        self,
        *,
        uids: list[int] | None = None,
        batch_uids: list[int] | None = None,
        index_uids: list[int] | None = None,
        statuses: list[str] | None = None,
        types: list[str] | None = None,
        limit: int = 20,
        from_: str | None = None,
        reverse: bool = False,
        before_enqueued_at: datetime | None = None,
        after_enqueued_at: datetime | None = None,
        before_started_at: datetime | None = None,
        after_finished_at: datetime | None = None,
    ) -> BatchStatus:
        return await async_get_batches(
            self,
            uids=uids,
            batch_uids=batch_uids,
            index_uids=index_uids,
            statuses=statuses,
            types=types,
            limit=limit,
            from_=from_,
            reverse=reverse,
            before_enqueued_at=before_enqueued_at,
            after_enqueued_at=after_enqueued_at,
            before_started_at=before_started_at,
            after_finished_at=after_finished_at,
        )

    async def cancel_tasks(
        self,
        *,
        uids: list[int] | None = None,
        index_uids: list[int] | None = None,
        statuses: list[str] | None = None,
        types: list[str] | None = None,
        before_enqueued_at: datetime | None = None,
        after_enqueued_at: datetime | None = None,
        before_started_at: datetime | None = None,
        after_finished_at: datetime | None = None,
    ) -> TaskInfo:
        """Cancel a list of enqueued or processing tasks.

        Defaults to cancelling all tasks.

        Args:
            uids: A list of task UIDs to cancel.
            index_uids: A list of index UIDs for which to cancel tasks.
            statuses: A list of statuses to cancel.
            types: A list of types to cancel.
            before_enqueued_at: Cancel tasks that were enqueued before the specified date time.
            after_enqueued_at: Cancel tasks that were enqueued after the specified date time.
            before_started_at: Cancel tasks that were started before the specified date time.
            after_finished_at: Cancel tasks that were finished after the specified date time.

        Returns:
            The details of the task

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.
            MeilisearchTimeoutError: If the connection times out.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>>
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     await client.cancel_tasks(uids=[1, 2])
        """
        return await _task.async_cancel_tasks(
            self.http_client,
            uids=uids,
            index_uids=index_uids,
            statuses=statuses,
            types=types,
            before_enqueued_at=before_enqueued_at,
            after_enqueued_at=after_enqueued_at,
            before_started_at=before_started_at,
            after_finished_at=after_finished_at,
        )

    async def get_task(self, task_id: int) -> TaskResult:
        """Get a single task from it's task id.

        Args:
            task_id: Identifier of the task to retrieve.

        Returns:
            Results of a task.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.
            MeilisearchTimeoutError: If the connection times out.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> from meilisearch_python_sdk.task import get_task
            >>>
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     await client.get_task(client, 1244)
        """
        return await _task.async_get_task(self.http_client, task_id=task_id)

    async def delete_tasks(
        self,
        *,
        uids: list[int] | None = None,
        index_uids: list[int] | None = None,
        statuses: list[str] | None = None,
        types: list[str] | None = None,
        before_enqueued_at: datetime | None = None,
        after_enqueued_at: datetime | None = None,
        before_started_at: datetime | None = None,
        after_finished_at: datetime | None = None,
    ) -> TaskInfo:
        """Delete a list of tasks.

        Defaults to deleting all tasks.

        Args:
            uids: A list of task UIDs to delete.
            index_uids: A list of index UIDs for which to delete tasks.
            statuses: A list of statuses to delete.
            types: A list of types to delete.
            before_enqueued_at: Delete tasks that were enqueued before the specified date time.
            after_enqueued_at: Delete tasks that were enqueued after the specified date time.
            before_started_at: Delete tasks that were started before the specified date time.
            after_finished_at: Delete tasks that were finished after the specified date time.

        Returns:
            The details of the task

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.
            MeilisearchTimeoutError: If the connection times out.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> from meilisearch_python_sdk.task import delete_tasks
            >>>
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     await client.delete_tasks(uids=[1, 2])
        """
        return await _task.async_delete_tasks(
            self.http_client,
            uids=uids,
            index_uids=index_uids,
            statuses=statuses,
            types=types,
            before_enqueued_at=before_enqueued_at,
            after_enqueued_at=after_enqueued_at,
            before_started_at=before_started_at,
            after_finished_at=after_finished_at,
        )

    async def get_tasks(
        self,
        *,
        index_ids: list[str] | None = None,
        types: str | list[str] | None = None,
        reverse: bool | None = None,
    ) -> TaskStatus:
        """Get multiple tasks.

        Args:
            index_ids: A list of index UIDs for which to get the tasks. If provided this will get the
                tasks only for the specified indexes, if not all tasks will be returned. Default = None
            types: Specify specific task types to retrieve. Default = None
            reverse: If True the tasks will be returned in reverse order. Default = None

        Returns:
            Task statuses.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.
            MeilisearchTimeoutError: If the connection times out.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>>
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     await client.get_tasks()
        """
        return await _task.async_get_tasks(
            self.http_client, index_ids=index_ids, types=types, reverse=reverse
        )

    async def wait_for_task(
        self,
        task_id: int,
        *,
        timeout_in_ms: int | None = 5000,
        interval_in_ms: int = 50,
        raise_for_status: bool = False,
    ) -> TaskResult:
        """Wait until Meilisearch processes a task, and get its status.

        Args:
            task_id: Identifier of the task to retrieve.
            timeout_in_ms: Amount of time in milliseconds to wait before raising a
                MeilisearchTimeoutError. `None` can also be passed to wait indefinitely. Be aware that
                if the `None` option is used the wait time could be very long. Defaults to 5000.
            interval_in_ms: Time interval in milliseconds to sleep between requests. Defaults to 50.
            raise_for_status: When set to `True` a MeilisearchTaskFailedError will be raised if a task
                has a failed status. Defaults to False.

        Returns:
            Details of the processed update status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.
            MeilisearchTimeoutError: If the connection times out.
            MeilisearchTaskFailedError: If `raise_for_status` is `True` and a task has a failed status.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> documents = [
            >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
            >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
            >>> ]
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     response = await index.add_documents(documents)
            >>>     await client.wait_for_task(client, response.update_id)
        """
        return await _task.async_wait_for_task(
            self.http_client,
            task_id=task_id,
            timeout_in_ms=timeout_in_ms,
            interval_in_ms=interval_in_ms,
            raise_for_status=raise_for_status,
        )

    # No cover because it requires multiple instances of Meilisearch
    async def transfer_documents(  # pragma: no cover
        self,
        url: str,
        *,
        api_key: str | None = None,
        payload_size: str | None = None,
        indexes: JsonMapping | None = None,
    ) -> TaskInfo:
        """Transfer settings and documents from one Meilisearch instance to another.

        Args:
            url: Where to send our settings and documents.
            api_key: The API key with the rights to send the requests. Usually the master key of
                the remote machine. Defaults to None.
            payload_size: Human readable size defining the size of the payloads to send. Defaults
                to 50 MiB.
            indexes: A set of patterns of matching the indexes you want to export. Defaults to all
                indexes without filter.

        Returns:
            The details of the task.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.
            MeilisearchTimeoutError: If the connection times out.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     await index.transfer_documents(
            >>>         "https://another-instance.com", api_key="otherMasterKey"
            >>>     )
        """
        payload = build_transfer_documents_payload(url, api_key, payload_size, indexes)

        response = await self._http_requests.post(url, body=payload)

        return TaskInfo(**self._http_requests.parse_json(response))

    async def get_experimental_features(self) -> dict[str, bool]:
        """Gets all experimental features and if they are enabled or not.

        Returns:
            The status of the experimental features.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.
            MeilisearchTimeoutError: If the connection times out.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     await index.get_experimental_feature()
        """

        response = await self._http_requests.get("/experimental-features")
        return self._http_requests.parse_json(response)

    async def update_experimental_features(self, features: dict[str, bool]) -> dict[str, bool]:
        """Update the status of an experimental feature.

        Args:
            features: Dictionary of features to enable/disable. The dictionary keys can be in either
                camel case or snake case, the conversion to the correct type will be handed for you by
                the program. For example {"logsRoute": True} and {"logs_route": True} will both work.

        Returns:
            The status of the experimental features.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.
            MeilisearchTimeoutError: If the connection times out.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     await index.update_experimental_features({"logsRoute": True})
        """
        payload = dict_to_camel(features)
        response = await self._http_requests.patch("/experimental-features", body=payload)

        return self._http_requests.parse_json(response)
