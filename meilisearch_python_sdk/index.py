from __future__ import annotations

import asyncio
from collections.abc import Generator, MutableMapping, Sequence
from csv import DictReader
from datetime import datetime
from functools import cached_property, partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlencode

import aiofiles
from camel_converter import to_snake
from httpx import AsyncClient, Client

from meilisearch_python_sdk._http_requests import AsyncHttpRequests, HttpRequests
from meilisearch_python_sdk._task import async_wait_for_task, wait_for_task
from meilisearch_python_sdk._utils import iso_to_date_time, use_task_groups
from meilisearch_python_sdk.errors import InvalidDocumentError, MeilisearchError
from meilisearch_python_sdk.json_handler import BuiltinHandler, OrjsonHandler, UjsonHandler
from meilisearch_python_sdk.models.documents import DocumentsInfo
from meilisearch_python_sdk.models.index import IndexStats
from meilisearch_python_sdk.models.search import (
    FacetSearchResults,
    Hybrid,
    SearchResults,
    SimilarSearchResults,
)
from meilisearch_python_sdk.models.settings import (
    CompositeEmbedder,
    Embedders,
    Faceting,
    FilterableAttributeFeatures,
    FilterableAttributes,
    HuggingFaceEmbedder,
    LocalizedAttributes,
    MeilisearchSettings,
    OllamaEmbedder,
    OpenAiEmbedder,
    Pagination,
    ProximityPrecision,
    RestEmbedder,
    TypoTolerance,
    UserProvidedEmbedder,
)
from meilisearch_python_sdk.models.task import TaskInfo
from meilisearch_python_sdk.plugins import (
    AsyncDocumentPlugin,
    AsyncEvent,
    AsyncIndexPlugins,
    AsyncPlugin,
    AsyncPostSearchPlugin,
    DocumentPlugin,
    Event,
    IndexPlugins,
    Plugin,
    PostSearchPlugin,
)
from meilisearch_python_sdk.types import JsonDict

if TYPE_CHECKING:  # pragma: no cover
    import sys

    from meilisearch_python_sdk.types import Filter, JsonMapping

    if sys.version_info >= (3, 11):
        from typing import Self
    else:
        from typing_extensions import Self


class _BaseIndex:
    def __init__(
        self,
        uid: str,
        primary_key: str | None = None,
        created_at: str | datetime | None = None,
        updated_at: str | datetime | None = None,
        json_handler: BuiltinHandler | OrjsonHandler | UjsonHandler | None = None,
        hits_type: Any = JsonDict,
    ):
        self.uid = uid
        self.primary_key = primary_key
        self.created_at: datetime | None = iso_to_date_time(created_at)
        self.updated_at: datetime | None = iso_to_date_time(updated_at)
        self.hits_type = hits_type
        self._base_url = "indexes/"
        self._base_url_with_uid = f"{self._base_url}{self.uid}"
        self._documents_url = f"{self._base_url_with_uid}/documents"
        self._stats_url = f"{self._base_url_with_uid}/stats"
        self._settings_url = f"{self._base_url_with_uid}/settings"
        self._json_handler = json_handler if json_handler else BuiltinHandler()

    def __str__(self) -> str:
        return f"{type(self).__name__}(uid={self.uid}, primary_key={self.primary_key}, created_at={self.created_at}, updated_at={self.updated_at})"

    def __repr__(self) -> str:
        return f"{type(self).__name__}(uid={self.uid!r}, primary_key={self.primary_key!r}, created_at={self.created_at!r}, updated_at={self.updated_at!r})"

    def _set_fetch_info(
        self, primary_key: str, created_at_iso_str: str, updated_at_iso_str: str
    ) -> None:
        self.primary_key = primary_key
        self.created_at = iso_to_date_time(created_at_iso_str)
        self.updated_at = iso_to_date_time(updated_at_iso_str)


class AsyncIndex(_BaseIndex):
    """AsyncIndex class gives access to all indexes routes and child routes.

    https://docs.meilisearch.com/reference/api/indexes.html
    """

    def __init__(
        self,
        http_client: AsyncClient,
        uid: str,
        primary_key: str | None = None,
        created_at: str | datetime | None = None,
        updated_at: str | datetime | None = None,
        plugins: AsyncIndexPlugins | None = None,
        json_handler: BuiltinHandler | OrjsonHandler | UjsonHandler | None = None,
        *,
        hits_type: Any = JsonDict,
    ):
        """Class initializer.

        Args:
            http_client: An instance of the AsyncClient. This automatically gets passed by the
                AsyncClient when creating and AsyncIndex instance.
            uid: The index's unique identifier.
            primary_key: The primary key of the documents. Defaults to None.
            created_at: The date and time the index was created. Defaults to None.
            updated_at: The date and time the index was last updated. Defaults to None.
            plugins: Optional plugins can be provided to extend functionality.
            json_handler: The module to use for json operations. The options are BuiltinHandler
                (uses the json module from the standard library), OrjsonHandler (uses orjson), or
                UjsonHandler (uses ujson). Note that in order use orjson or ujson the corresponding
                extra needs to be included. Default: BuiltinHandler.
            hits_type: Allows for a custom type to be passed to use for hits. Defaults to
                JsonDict
        """
        super().__init__(
            uid=uid,
            primary_key=primary_key,
            created_at=created_at,
            updated_at=updated_at,
            json_handler=json_handler,
            hits_type=hits_type,
        )
        self.http_client = http_client
        self._http_requests = AsyncHttpRequests(http_client, json_handler=self._json_handler)
        self.plugins = plugins

    @cached_property
    def _concurrent_add_documents_plugins(self) -> list[AsyncPlugin | AsyncDocumentPlugin] | None:
        if not self.plugins or not self.plugins.add_documents_plugins:
            return None

        plugins = [
            plugin for plugin in self.plugins.add_documents_plugins if plugin.CONCURRENT_EVENT
        ]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _post_add_documents_plugins(self) -> list[AsyncPlugin | AsyncDocumentPlugin] | None:
        if not self.plugins or not self.plugins.add_documents_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.add_documents_plugins if plugin.POST_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _pre_add_documents_plugins(self) -> list[AsyncPlugin | AsyncDocumentPlugin] | None:
        if not self.plugins or not self.plugins.add_documents_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.add_documents_plugins if plugin.PRE_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _concurrent_delete_all_documents_plugins(self) -> list[AsyncPlugin] | None:
        if not self.plugins or not self.plugins.delete_all_documents_plugins:
            return None

        plugins = [
            plugin
            for plugin in self.plugins.delete_all_documents_plugins
            if plugin.CONCURRENT_EVENT
        ]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _post_delete_all_documents_plugins(self) -> list[AsyncPlugin] | None:
        if not self.plugins or not self.plugins.delete_all_documents_plugins:
            return None

        plugins = [
            plugin for plugin in self.plugins.delete_all_documents_plugins if plugin.POST_EVENT
        ]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _pre_delete_all_documents_plugins(self) -> list[AsyncPlugin] | None:
        if not self.plugins or not self.plugins.delete_all_documents_plugins:
            return None

        plugins = [
            plugin for plugin in self.plugins.delete_all_documents_plugins if plugin.PRE_EVENT
        ]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _concurrent_delete_document_plugins(self) -> list[AsyncPlugin] | None:
        if not self.plugins or not self.plugins.delete_document_plugins:
            return None

        plugins = [
            plugin for plugin in self.plugins.delete_document_plugins if plugin.CONCURRENT_EVENT
        ]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _post_delete_document_plugins(self) -> list[AsyncPlugin] | None:
        if not self.plugins or not self.plugins.delete_document_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.delete_document_plugins if plugin.POST_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _pre_delete_document_plugins(self) -> list[AsyncPlugin] | None:
        if not self.plugins or not self.plugins.delete_document_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.delete_document_plugins if plugin.PRE_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _concurrent_delete_documents_plugins(self) -> list[AsyncPlugin] | None:
        if not self.plugins or not self.plugins.delete_documents_plugins:
            return None

        plugins = [
            plugin for plugin in self.plugins.delete_documents_plugins if plugin.CONCURRENT_EVENT
        ]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _post_delete_documents_plugins(self) -> list[AsyncPlugin] | None:
        if not self.plugins or not self.plugins.delete_documents_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.delete_documents_plugins if plugin.POST_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _pre_delete_documents_plugins(self) -> list[AsyncPlugin] | None:
        if not self.plugins or not self.plugins.delete_documents_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.delete_documents_plugins if plugin.PRE_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _concurrent_delete_documents_by_filter_plugins(self) -> list[AsyncPlugin] | None:
        if not self.plugins or not self.plugins.delete_documents_by_filter_plugins:
            return None

        plugins = [
            plugin
            for plugin in self.plugins.delete_documents_by_filter_plugins
            if plugin.CONCURRENT_EVENT
        ]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _post_delete_documents_by_filter_plugins(self) -> list[AsyncPlugin] | None:
        if not self.plugins or not self.plugins.delete_documents_by_filter_plugins:
            return None

        plugins = [
            plugin
            for plugin in self.plugins.delete_documents_by_filter_plugins
            if plugin.POST_EVENT
        ]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _pre_delete_documents_by_filter_plugins(self) -> list[AsyncPlugin] | None:
        if not self.plugins or not self.plugins.delete_documents_by_filter_plugins:
            return None

        plugins = [
            plugin for plugin in self.plugins.delete_documents_by_filter_plugins if plugin.PRE_EVENT
        ]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _concurrent_facet_search_plugins(self) -> list[AsyncPlugin] | None:
        if not self.plugins or not self.plugins.facet_search_plugins:
            return None

        plugins = [
            plugin for plugin in self.plugins.facet_search_plugins if plugin.CONCURRENT_EVENT
        ]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _post_facet_search_plugins(self) -> list[AsyncPlugin] | None:
        if not self.plugins or not self.plugins.facet_search_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.facet_search_plugins if plugin.POST_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _pre_facet_search_plugins(self) -> list[AsyncPlugin] | None:
        if not self.plugins or not self.plugins.facet_search_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.facet_search_plugins if plugin.PRE_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _concurrent_search_plugins(self) -> list[AsyncPlugin | AsyncPostSearchPlugin] | None:
        if not self.plugins or not self.plugins.search_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.search_plugins if plugin.CONCURRENT_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _post_search_plugins(self) -> list[AsyncPlugin | AsyncPostSearchPlugin] | None:
        if not self.plugins or not self.plugins.search_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.search_plugins if plugin.POST_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _pre_search_plugins(self) -> list[AsyncPlugin | AsyncPostSearchPlugin] | None:
        if not self.plugins or not self.plugins.search_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.search_plugins if plugin.PRE_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _concurrent_update_documents_plugins(
        self,
    ) -> list[AsyncPlugin | AsyncDocumentPlugin] | None:
        if not self.plugins or not self.plugins.update_documents_plugins:
            return None

        plugins = [
            plugin for plugin in self.plugins.update_documents_plugins if plugin.CONCURRENT_EVENT
        ]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _post_update_documents_plugins(self) -> list[AsyncPlugin | AsyncDocumentPlugin] | None:
        if not self.plugins or not self.plugins.update_documents_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.update_documents_plugins if plugin.POST_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _pre_update_documents_plugins(self) -> list[AsyncPlugin | AsyncDocumentPlugin] | None:
        if not self.plugins or not self.plugins.update_documents_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.update_documents_plugins if plugin.PRE_EVENT]

        if not plugins:
            return None

        return plugins

    async def delete(self) -> TaskInfo:
        """Deletes the index.

        Returns:
            The details of the task.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.delete()
        """
        response = await self._http_requests.delete(self._base_url_with_uid)
        return TaskInfo(**response.json())

    async def delete_if_exists(self) -> bool:
        """Delete the index if it already exists.

        Returns:
            True if the index was deleted or False if not.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.delete_if_exists()
        """
        response = await self.delete()
        status = await async_wait_for_task(
            self.http_client, response.task_uid, timeout_in_ms=100000
        )
        if status.status == "succeeded":
            return True

        return False

    async def update(self, primary_key: str) -> Self:
        """Update the index primary key.

        Args:
            primary_key: The primary key of the documents.

        Returns:
            An instance of the AsyncIndex with the updated information.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     updated_index = await index.update()
        """
        payload = {"primaryKey": primary_key}
        response = await self._http_requests.patch(self._base_url_with_uid, payload)
        await async_wait_for_task(
            self.http_client, response.json()["taskUid"], timeout_in_ms=100000
        )
        index_response = await self._http_requests.get(f"{self._base_url_with_uid}")
        self.primary_key = index_response.json()["primaryKey"]
        return self

    async def fetch_info(self) -> Self:
        """Gets the infromation about the index.

        Returns:
            An instance of the AsyncIndex containing the retrieved information.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     index_info = await index.fetch_info()
        """
        response = await self._http_requests.get(self._base_url_with_uid)
        index_dict = response.json()
        self._set_fetch_info(
            index_dict["primaryKey"], index_dict["createdAt"], index_dict["updatedAt"]
        )
        return self

    async def get_primary_key(self) -> str | None:
        """Get the primary key.

        Returns:
            The primary key for the documents in the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     primary_key = await index.get_primary_key()
        """
        info = await self.fetch_info()
        return info.primary_key

    @classmethod
    async def create(
        cls,
        http_client: AsyncClient,
        uid: str,
        primary_key: str | None = None,
        *,
        settings: MeilisearchSettings | None = None,
        wait: bool = True,
        timeout_in_ms: int | None = None,
        plugins: AsyncIndexPlugins | None = None,
        json_handler: BuiltinHandler | OrjsonHandler | UjsonHandler | None = None,
        hits_type: Any = JsonDict,
    ) -> Self:
        """Creates a new index.

        In general this method should not be used directly and instead the index should be created
        through the `Client`.

        Args:
            http_client: An instance of the AsyncClient. This automatically gets passed by the
                Client when creating an AsyncIndex instance.
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
            json_handler: The module to use for json operations. The options are BuiltinHandler
                (uses the json module from the standard library), OrjsonHandler (uses orjson), or
                UjsonHandler (uses ujson). Note that in order use orjson or ujson the corresponding
                extra needs to be included. Default: BuiltinHandler.
            hits_type: Allows for a custom type to be passed to use for hits. Defaults to
                JsonDict

        Returns:
            An instance of AsyncIndex containing the information of the newly created index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = await index.create(client, "movies")
        """
        if not primary_key:
            payload = {"uid": uid}
        else:
            payload = {"primaryKey": primary_key, "uid": uid}

        url = "indexes"
        handler = json_handler if json_handler else BuiltinHandler()
        http_request = AsyncHttpRequests(http_client, json_handler=handler)
        response = await http_request.post(url, payload)
        await async_wait_for_task(
            http_client,
            response.json()["taskUid"],
            timeout_in_ms=timeout_in_ms,
        )

        index_response = await http_request.get(f"{url}/{uid}")
        index_dict = index_response.json()
        index = cls(
            http_client=http_client,
            uid=index_dict["uid"],
            primary_key=index_dict["primaryKey"],
            created_at=index_dict["createdAt"],
            updated_at=index_dict["updatedAt"],
            plugins=plugins,
            json_handler=json_handler,
            hits_type=hits_type,
        )

        if settings:
            settings_task = await index.update_settings(settings)
            if wait:
                await async_wait_for_task(
                    http_client, settings_task.task_uid, timeout_in_ms=timeout_in_ms
                )

        return index

    async def get_stats(self) -> IndexStats:
        """Get stats of the index.

        Returns:
            Stats of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     stats = await index.get_stats()
        """
        response = await self._http_requests.get(self._stats_url)

        return IndexStats(**response.json())

    async def search(
        self,
        query: str | None = None,
        *,
        offset: int = 0,
        limit: int = 20,
        filter: Filter | None = None,
        facets: list[str] | None = None,
        attributes_to_retrieve: list[str] | None = None,
        attributes_to_crop: list[str] | None = None,
        crop_length: int = 200,
        attributes_to_highlight: list[str] | None = None,
        sort: list[str] | None = None,
        show_matches_position: bool = False,
        highlight_pre_tag: str = "<em>",
        highlight_post_tag: str = "</em>",
        crop_marker: str = "...",
        matching_strategy: Literal["all", "last", "frequency"] = "last",
        hits_per_page: int | None = None,
        page: int | None = None,
        attributes_to_search_on: list[str] | None = None,
        distinct: str | None = None,
        show_ranking_score: bool = False,
        show_ranking_score_details: bool = False,
        ranking_score_threshold: float | None = None,
        vector: list[float] | None = None,
        hybrid: Hybrid | None = None,
        locales: list[str] | None = None,
        retrieve_vectors: bool | None = None,
    ) -> SearchResults:
        """Search the index.

        Args:
            query: String containing the word(s) to search
            offset: Number of documents to skip. Defaults to 0.
            limit: Maximum number of documents returned. Defaults to 20.
            filter: Filter queries by an attribute value. Defaults to None.
            facets: Facets for which to retrieve the matching count. Defaults to None.
            attributes_to_retrieve: Attributes to display in the returned documents.
                Defaults to ["*"].
            attributes_to_crop: Attributes whose values have to be cropped. Defaults to None.
            crop_length: The maximun number of words to display. Defaults to 200.
            attributes_to_highlight: Attributes whose values will contain highlighted matching terms.
                Defaults to None.
            sort: Attributes by which to sort the results. Defaults to None.
            show_matches_position: Defines whether an object that contains information about the
                matches should be returned or not. Defaults to False.
            highlight_pre_tag: The opening tag for highlighting text. Defaults to <em>.
            highlight_post_tag: The closing tag for highlighting text. Defaults to </em>
            crop_marker: Marker to display when the number of words excedes the `crop_length`.
                Defaults to ...
            matching_strategy: Specifies the matching strategy Meilisearch should use. Defaults to
                `last`.
            hits_per_page: Sets the number of results returned per page.
            page: Sets the specific results page to fetch.
            attributes_to_search_on: List of field names. Allow search over a subset of searchable
                attributes without modifying the index settings. Defaults to None.
            distinct: If set the distinct value will return at most one result for the
                filterable attribute. Note that a filterable attributes must be set for this work.
                Defaults to None.
            show_ranking_score: If set to True the ranking score will be returned with each document
                in the search. Defaults to False.
            show_ranking_score_details: If set to True the ranking details will be returned with
                each document in the search. Defaults to False. Note: This parameter can only be
                used with Meilisearch >= v1.3.0, and is experimental in Meilisearch v1.3.0. In order
                to use this feature in Meilisearch v1.3.0 you first need to enable the feature by
                sending a PATCH request to /experimental-features with { "scoreDetails": true }.
                Because this feature is experimental it may be removed or updated causing breaking
                changes in this library without a major version bump so use with caution. This
                feature became stable in Meiliseach v1.7.0.
            ranking_score_threshold: If set, no document whose _rankingScore is under the
                rankingScoreThreshold is returned. The value must be between 0.0 and 1.0. Defaults
                to None.
            vector: List of vectors for vector search. Defaults to None. Note: This parameter can
                only be used with Meilisearch >= v1.3.0, and is experimental in Meilisearch v1.3.0.
                In order to use this feature in Meilisearch v1.3.0 you first need to enable the
                feature by sending a PATCH request to /experimental-features with
                { "vectorStore": true }. Because this feature is experimental it may be removed or
                updated causing breaking changes in this library without a major version bump so use
                with caution.
            hybrid: Hybrid search information. Defaults to None. Note: This parameter can
                only be used with Meilisearch >= v1.6.0, and is experimental in Meilisearch v1.6.0.
                In order to use this feature in Meilisearch v1.6.0 you first need to enable the
                feature by sending a PATCH request to /experimental-features with
                { "vectorStore": true }. Because this feature is experimental it may be removed or
                updated causing breaking changes in this library without a major version bump so use
                with caution.
            locales: Specifies the languages for the search. This parameter can only be used with
                Milisearch >= v1.10.0. Defaults to None letting the Meilisearch pick.
            retrieve_vectors: Return document vector data with search result.

        Returns:
            Results of the search

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     search_results = await index.search("Tron")
        """
        if ranking_score_threshold:
            _validate_ranking_score_threshold(ranking_score_threshold)

        body = _process_search_parameters(
            q=query,
            offset=offset,
            limit=limit,
            filter=filter,
            facets=facets,
            attributes_to_retrieve=attributes_to_retrieve,
            attributes_to_crop=attributes_to_crop,
            crop_length=crop_length,
            attributes_to_highlight=attributes_to_highlight,
            sort=sort,
            show_matches_position=show_matches_position,
            highlight_pre_tag=highlight_pre_tag,
            highlight_post_tag=highlight_post_tag,
            crop_marker=crop_marker,
            matching_strategy=matching_strategy,
            hits_per_page=hits_per_page,
            page=page,
            attributes_to_search_on=attributes_to_search_on,
            distinct=distinct,
            show_ranking_score=show_ranking_score,
            show_ranking_score_details=show_ranking_score_details,
            vector=vector,
            hybrid=hybrid,
            ranking_score_threshold=ranking_score_threshold,
            locales=locales,
            retrieve_vectors=retrieve_vectors,
        )
        search_url = f"{self._base_url_with_uid}/search"

        if self._pre_search_plugins:
            await AsyncIndex._run_plugins(
                self._pre_search_plugins,
                AsyncEvent.PRE,
                query=query,
                offset=offset,
                limit=limit,
                filter=filter,
                facets=facets,
                attributes_to_retrieve=attributes_to_retrieve,
                attributes_to_crop=attributes_to_crop,
                crop_length=crop_length,
                attributes_to_highlight=attributes_to_highlight,
                sort=sort,
                show_matches_position=show_matches_position,
                highlight_pre_tag=highlight_pre_tag,
                highlight_post_tag=highlight_post_tag,
                crop_marker=crop_marker,
                matching_strategy=matching_strategy,
                hits_per_page=hits_per_page,
                page=page,
                attributes_to_search_on=attributes_to_search_on,
                distinct=distinct,
                show_ranking_score=show_ranking_score,
                show_ranking_score_details=show_ranking_score_details,
                vector=vector,
                hybrid=hybrid,
            )

        if self._concurrent_search_plugins:
            if not use_task_groups():
                concurrent_tasks: Any = []
                for plugin in self._concurrent_search_plugins:
                    if _plugin_has_method(plugin, "run_plugin"):
                        concurrent_tasks.append(
                            plugin.run_plugin(  # type: ignore[union-attr]
                                event=AsyncEvent.CONCURRENT,
                                query=query,
                                offset=offset,
                                limit=limit,
                                filter=filter,
                                facets=facets,
                                attributes_to_retrieve=attributes_to_retrieve,
                                attributes_to_crop=attributes_to_crop,
                                crop_length=crop_length,
                                attributes_to_highlight=attributes_to_highlight,
                                sort=sort,
                                show_matches_position=show_matches_position,
                                highlight_pre_tag=highlight_pre_tag,
                                highlight_post_tag=highlight_post_tag,
                                crop_marker=crop_marker,
                                matching_strategy=matching_strategy,
                                hits_per_page=hits_per_page,
                                page=page,
                                attributes_to_search_on=attributes_to_search_on,
                                distinct=distinct,
                                show_ranking_score=show_ranking_score,
                                show_ranking_score_details=show_ranking_score_details,
                                vector=vector,
                            )
                        )

                concurrent_tasks.append(self._http_requests.post(search_url, body=body))

                responses = await asyncio.gather(*concurrent_tasks)
                result = SearchResults[self.hits_type](**responses[-1].json())  # type: ignore[name-defined]
                if self._post_search_plugins:
                    post = await AsyncIndex._run_plugins(
                        self._post_search_plugins, AsyncEvent.POST, search_results=result
                    )
                    if post.get("search_result"):
                        result = post["search_result"]

                return result

            async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
                for plugin in self._concurrent_search_plugins:
                    if _plugin_has_method(plugin, "run_plugin"):
                        tg.create_task(
                            plugin.run_plugin(  # type: ignore[union-attr]
                                event=AsyncEvent.CONCURRENT,
                                query=query,
                                offset=offset,
                                limit=limit,
                                filter=filter,
                                facets=facets,
                                attributes_to_retrieve=attributes_to_retrieve,
                                attributes_to_crop=attributes_to_crop,
                                crop_length=crop_length,
                                attributes_to_highlight=attributes_to_highlight,
                                sort=sort,
                                show_matches_position=show_matches_position,
                                highlight_pre_tag=highlight_pre_tag,
                                highlight_post_tag=highlight_post_tag,
                                crop_marker=crop_marker,
                                matching_strategy=matching_strategy,
                                hits_per_page=hits_per_page,
                                page=page,
                                attributes_to_search_on=attributes_to_search_on,
                                distinct=distinct,
                                show_ranking_score=show_ranking_score,
                                show_ranking_score_details=show_ranking_score_details,
                                vector=vector,
                            )
                        )

                response_coroutine = tg.create_task(self._http_requests.post(search_url, body=body))

            response = await response_coroutine
            result = SearchResults[self.hits_type](**response.json())  # type: ignore[name-defined]
            if self._post_search_plugins:
                post = await AsyncIndex._run_plugins(
                    self._post_search_plugins, AsyncEvent.POST, search_results=result
                )
                if post.get("search_result"):
                    result = post["search_result"]

            return result

        response = await self._http_requests.post(search_url, body=body)
        result = SearchResults[self.hits_type](**response.json())  # type: ignore[name-defined]

        if self._post_search_plugins:
            post = await AsyncIndex._run_plugins(
                self._post_search_plugins, AsyncEvent.POST, search_results=result
            )
            if post.get("search_result"):
                result = post["search_result"]

        return result

    async def facet_search(
        self,
        query: str | None = None,
        *,
        facet_name: str,
        facet_query: str,
        offset: int = 0,
        limit: int = 20,
        filter: Filter | None = None,
        facets: list[str] | None = None,
        attributes_to_retrieve: list[str] | None = None,
        attributes_to_crop: list[str] | None = None,
        crop_length: int = 200,
        attributes_to_highlight: list[str] | None = None,
        sort: list[str] | None = None,
        show_matches_position: bool = False,
        highlight_pre_tag: str = "<em>",
        highlight_post_tag: str = "</em>",
        crop_marker: str = "...",
        matching_strategy: Literal["all", "last", "frequency"] = "last",
        hits_per_page: int | None = None,
        page: int | None = None,
        attributes_to_search_on: list[str] | None = None,
        show_ranking_score: bool = False,
        show_ranking_score_details: bool = False,
        ranking_score_threshold: float | None = None,
        vector: list[float] | None = None,
        locales: list[str] | None = None,
        retrieve_vectors: bool | None = None,
        exhaustive_facet_count: bool | None = None,
    ) -> FacetSearchResults:
        """Search the index.

        Args:
            query: String containing the word(s) to search
            facet_name: The name of the facet to search
            facet_query: The facet search value
            offset: Number of documents to skip. Defaults to 0.
            limit: Maximum number of documents returned. Defaults to 20.
            filter: Filter queries by an attribute value. Defaults to None.
            facets: Facets for which to retrieve the matching count. Defaults to None.
            attributes_to_retrieve: Attributes to display in the returned documents.
                Defaults to ["*"].
            attributes_to_crop: Attributes whose values have to be cropped. Defaults to None.
            crop_length: The maximun number of words to display. Defaults to 200.
            attributes_to_highlight: Attributes whose values will contain highlighted matching terms.
                Defaults to None.
            sort: Attributes by which to sort the results. Defaults to None.
            show_matches_position: Defines whether an object that contains information about the
                matches should be returned or not. Defaults to False.
            highlight_pre_tag: The opening tag for highlighting text. Defaults to <em>.
            highlight_post_tag: The closing tag for highlighting text. Defaults to </em>
            crop_marker: Marker to display when the number of words excedes the `crop_length`.
                Defaults to ...
            matching_strategy: Specifies the matching strategy Meilisearch should use. Defaults to
                `last`.
            hits_per_page: Sets the number of results returned per page.
            page: Sets the specific results page to fetch.
            attributes_to_search_on: List of field names. Allow search over a subset of searchable
                attributes without modifying the index settings. Defaults to None.
            show_ranking_score: If set to True the ranking score will be returned with each document
                in the search. Defaults to False.
            show_ranking_score_details: If set to True the ranking details will be returned with
                each document in the search. Defaults to False. Note: This parameter can only be
                used with Meilisearch >= v1.3.0, and is experimental in Meilisearch v1.3.0. In order
                to use this feature in Meilisearch v1.3.0 you first need to enable the feature by
                sending a PATCH request to /experimental-features with { "scoreDetails": true }.
                Because this feature is experimental it may be removed or updated causing breaking
                changes in this library without a major version bump so use with caution. This
                feature became stable in Meiliseach v1.7.0.
            ranking_score_threshold: If set, no document whose _rankingScore is under the
                rankingScoreThreshold is returned. The value must be between 0.0 and 1.0. Defaults
                to None.
            vector: List of vectors for vector search. Defaults to None. Note: This parameter can
                only be used with Meilisearch >= v1.3.0, and is experimental in Meilisearch v1.3.0.
                In order to use this feature in Meilisearch v1.3.0 you first need to enable the
                feature by sending a PATCH request to /experimental-features with
                { "vectorStore": true }. Because this feature is experimental it may be removed or
                updated causing breaking changes in this library without a major version bump so use
                with caution.
            locales: Specifies the languages for the search. This parameter can only be used with
                Milisearch >= v1.10.0. Defaults to None letting the Meilisearch pick.
            retrieve_vectors: Return document vector data with search result.
            exhaustive_facet_count: forcing the facet search to compute the facet counts the same
                way as the paginated search. This parameter can only be used with Milisearch >=
                v1.14.0. Defaults to None.

        Returns:
            Results of the search

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     search_results = await index.search(
            >>>         "Tron",
            >>>         facet_name="genre",
            >>>         facet_query="Sci-fi"
            >>>     )
        """
        if ranking_score_threshold:
            _validate_ranking_score_threshold(ranking_score_threshold)

        body = _process_search_parameters(
            q=query,
            facet_name=facet_name,
            facet_query=facet_query,
            offset=offset,
            limit=limit,
            filter=filter,
            facets=facets,
            attributes_to_retrieve=attributes_to_retrieve,
            attributes_to_crop=attributes_to_crop,
            crop_length=crop_length,
            attributes_to_highlight=attributes_to_highlight,
            sort=sort,
            show_matches_position=show_matches_position,
            highlight_pre_tag=highlight_pre_tag,
            highlight_post_tag=highlight_post_tag,
            crop_marker=crop_marker,
            matching_strategy=matching_strategy,
            hits_per_page=hits_per_page,
            page=page,
            attributes_to_search_on=attributes_to_search_on,
            show_ranking_score=show_ranking_score,
            show_ranking_score_details=show_ranking_score_details,
            ranking_score_threshold=ranking_score_threshold,
            vector=vector,
            locales=locales,
            retrieve_vectors=retrieve_vectors,
            exhaustive_facet_count=exhaustive_facet_count,
        )
        search_url = f"{self._base_url_with_uid}/facet-search"

        if self._pre_facet_search_plugins:
            await AsyncIndex._run_plugins(
                self._pre_facet_search_plugins,
                AsyncEvent.PRE,
                query=query,
                offset=offset,
                limit=limit,
                filter=filter,
                facets=facets,
                attributes_to_retrieve=attributes_to_retrieve,
                attributes_to_crop=attributes_to_crop,
                crop_length=crop_length,
                attributes_to_highlight=attributes_to_highlight,
                sort=sort,
                show_matches_position=show_matches_position,
                highlight_pre_tag=highlight_pre_tag,
                highlight_post_tag=highlight_post_tag,
                crop_marker=crop_marker,
                matching_strategy=matching_strategy,
                hits_per_page=hits_per_page,
                page=page,
                attributes_to_search_on=attributes_to_search_on,
                show_ranking_score=show_ranking_score,
                show_ranking_score_details=show_ranking_score_details,
                ranking_score_threshold=ranking_score_threshold,
                vector=vector,
                exhaustive_facet_count=exhaustive_facet_count,
            )

        if self._concurrent_facet_search_plugins:
            if not use_task_groups():
                tasks: Any = []
                for plugin in self._concurrent_facet_search_plugins:
                    if _plugin_has_method(plugin, "run_plugin"):
                        tasks.append(
                            plugin.run_plugin(  # type: ignore[union-attr]
                                event=AsyncEvent.CONCURRENT,
                                query=query,
                                offset=offset,
                                limit=limit,
                                filter=filter,
                                facets=facets,
                                attributes_to_retrieve=attributes_to_retrieve,
                                attributes_to_crop=attributes_to_crop,
                                crop_length=crop_length,
                                attributes_to_highlight=attributes_to_highlight,
                                sort=sort,
                                show_matches_position=show_matches_position,
                                highlight_pre_tag=highlight_pre_tag,
                                highlight_post_tag=highlight_post_tag,
                                crop_marker=crop_marker,
                                matching_strategy=matching_strategy,
                                hits_per_page=hits_per_page,
                                page=page,
                                attributes_to_search_on=attributes_to_search_on,
                                show_ranking_score=show_ranking_score,
                                show_ranking_score_details=show_ranking_score_details,
                                ranking_score_threshold=ranking_score_threshold,
                                vector=vector,
                                exhaustive_facet_count=exhaustive_facet_count,
                            )
                        )

                tasks.append(self._http_requests.post(search_url, body=body))
                responses = await asyncio.gather(*tasks)
                result = FacetSearchResults(**responses[-1].json())
                if self._post_facet_search_plugins:
                    post = await AsyncIndex._run_plugins(
                        self._post_facet_search_plugins, AsyncEvent.POST, result=result
                    )
                    if isinstance(post["generic_result"], FacetSearchResults):
                        result = post["generic_result"]

                return result

            async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
                for plugin in self._concurrent_facet_search_plugins:
                    if _plugin_has_method(plugin, "run_plugin"):
                        tg.create_task(
                            plugin.run_plugin(  # type: ignore[union-attr]
                                event=AsyncEvent.CONCURRENT,
                                query=query,
                                offset=offset,
                                limit=limit,
                                filter=filter,
                                facets=facets,
                                attributes_to_retrieve=attributes_to_retrieve,
                                attributes_to_crop=attributes_to_crop,
                                crop_length=crop_length,
                                attributes_to_highlight=attributes_to_highlight,
                                sort=sort,
                                show_matches_position=show_matches_position,
                                highlight_pre_tag=highlight_pre_tag,
                                highlight_post_tag=highlight_post_tag,
                                crop_marker=crop_marker,
                                matching_strategy=matching_strategy,
                                hits_per_page=hits_per_page,
                                page=page,
                                attributes_to_search_on=attributes_to_search_on,
                                show_ranking_score=show_ranking_score,
                                show_ranking_score_details=show_ranking_score_details,
                                ranking_score_threshold=ranking_score_threshold,
                                vector=vector,
                                exhaustive_facet_count=exhaustive_facet_count,
                            )
                        )

                response_coroutine = tg.create_task(self._http_requests.post(search_url, body=body))

            response = await response_coroutine
            result = FacetSearchResults(**response.json())
            if self._post_facet_search_plugins:
                post = await AsyncIndex._run_plugins(
                    self._post_facet_search_plugins, AsyncEvent.POST, result=result
                )
                if isinstance(post["generic_result"], FacetSearchResults):
                    result = post["generic_result"]

            return result

        response = await self._http_requests.post(search_url, body=body)
        result = FacetSearchResults(**response.json())
        if self._post_facet_search_plugins:
            post = await AsyncIndex._run_plugins(
                self._post_facet_search_plugins, AsyncEvent.POST, result=result
            )
            if isinstance(post["generic_result"], FacetSearchResults):
                result = post["generic_result"]

        return result

    async def search_similar_documents(
        self,
        id: str,
        *,
        offset: int | None = None,
        limit: int | None = None,
        filter: str | None = None,
        embedder: str = "default",
        attributes_to_retrieve: list[str] | None = None,
        show_ranking_score: bool = False,
        show_ranking_score_details: bool = False,
        ranking_score_threshold: float | None = None,
    ) -> SimilarSearchResults:
        """Search the index.

        Args:
            id: The id for the target document that is being used to find similar documents.
            offset: Number of documents to skip. Defaults to 0.
            limit: Maximum number of documents returned. Defaults to 20.
            filter: Filter queries by an attribute value. Defaults to None.
            embedder: The vector DB to use for the search.
            attributes_to_retrieve: Attributes to display in the returned documents.
                Defaults to ["*"].
            show_ranking_score: If set to True the ranking score will be returned with each document
                in the search. Defaults to False.
            show_ranking_score_details: If set to True the ranking details will be returned with
                each document in the search. Defaults to False.
            ranking_score_threshold: If set, no document whose _rankingScore is under the
                rankingScoreThreshold is returned. The value must be between 0.0 and 1.0. Defaults
                to None.

        Returns:
            Results of the search

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     search_results = await index.search_similar_documents("123")
        """
        payload = {
            "id": id,
            "filter": filter,
            "embedder": embedder,
            "attributesToRetrieve": attributes_to_retrieve,
            "showRankingScore": show_ranking_score,
            "showRankingScoreDetails": show_ranking_score_details,
            "rankingScoreThreshold": ranking_score_threshold,
        }

        if offset:
            payload["offset"] = offset

        if limit:
            payload["limit"] = limit

        response = await self._http_requests.post(
            f"{self._base_url_with_uid}/similar", body=payload
        )

        return SimilarSearchResults[self.hits_type](**response.json())  # type: ignore[name-defined]

    async def get_document(
        self,
        document_id: str,
        *,
        fields: list[str] | None = None,
        retrieve_vectors: bool = False,
    ) -> JsonDict:
        """Get one document with given document identifier.

        Args:
            document_id: Unique identifier of the document.
            fields: Document attributes to show. If this value is None then all
                attributes are retrieved. Defaults to None.
            retrieve_vectors: If set to True the embedding vectors will be returned with the document.
                Defaults to False. Note: This parameter can only be
                used with Meilisearch >= v1.13.0
        Returns:
            The document information

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     document = await index.get_document("1234")
        """
        parameters: JsonDict = {}

        if fields:
            parameters["fields"] = ",".join(fields)
        if retrieve_vectors:
            parameters["retrieveVectors"] = "true"

        url = _build_encoded_url(f"{self._documents_url}/{document_id}", parameters)

        response = await self._http_requests.get(url)

        return response.json()

    async def get_documents(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        fields: list[str] | None = None,
        filter: Filter | None = None,
        retrieve_vectors: bool = False,
    ) -> DocumentsInfo:
        """Get a batch documents from the index.

        Args:
            offset: Number of documents to skip. Defaults to 0.
            limit: Maximum number of documents returnedd. Defaults to 20.
            fields: Document attributes to show. If this value is None then all
                attributes are retrieved. Defaults to None.
            filter: Filter value information. Defaults to None. Note: This parameter can only be
                used with Meilisearch >= v1.2.0
            retrieve_vectors: If set to True the vectors will be returned with each document.
                Defaults to False. Note: This parameter can only be
                used with Meilisearch >= v1.13.0

        Returns:
            Documents info.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.


        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     documents = await index.get_documents()
        """
        parameters: JsonDict = {
            "offset": offset,
            "limit": limit,
        }

        if retrieve_vectors:
            parameters["retrieveVectors"] = "true"

        if not filter:
            if fields:
                parameters["fields"] = ",".join(fields)

            url = _build_encoded_url(self._documents_url, parameters)
            response = await self._http_requests.get(url)

            return DocumentsInfo(**response.json())

        if fields:
            parameters["fields"] = fields

        parameters["filter"] = filter

        response = await self._http_requests.post(f"{self._documents_url}/fetch", body=parameters)

        return DocumentsInfo(**response.json())

    async def add_documents(
        self,
        documents: Sequence[JsonMapping],
        primary_key: str | None = None,
        *,
        compress: bool = False,
    ) -> TaskInfo:
        """Add documents to the index.

        Args:
            documents: List of documents.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> documents = [
            >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
            >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
            >>> ]
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.add_documents(documents)
        """
        if primary_key:
            url = _build_encoded_url(self._documents_url, {"primaryKey": primary_key})
        else:
            url = self._documents_url

        if self._pre_add_documents_plugins:
            pre = await AsyncIndex._run_plugins(
                self._pre_add_documents_plugins,
                AsyncEvent.PRE,
                documents=documents,
                primary_key=primary_key,
            )
            if pre.get("document_result"):
                documents = pre["document_result"]

        if self._concurrent_add_documents_plugins:
            if not use_task_groups():
                tasks: Any = []
                for plugin in self._concurrent_add_documents_plugins:
                    if _plugin_has_method(plugin, "run_plugin"):
                        tasks.append(
                            plugin.run_plugin(  # type: ignore[union-attr]
                                event=AsyncEvent.CONCURRENT,
                                documents=documents,
                                primary_key=primary_key,
                            )
                        )
                    if _plugin_has_method(plugin, "run_document_plugin"):
                        tasks.append(
                            plugin.run_document_plugin(  # type: ignore[union-attr]
                                event=AsyncEvent.CONCURRENT,
                                documents=documents,
                                primary_key=primary_key,
                            )
                        )

                tasks.append(self._http_requests.post(url, documents, compress=compress))

                responses = await asyncio.gather(*tasks)
                result = TaskInfo(**responses[-1].json())
                if self._post_add_documents_plugins:
                    post = await AsyncIndex._run_plugins(
                        self._post_add_documents_plugins,
                        AsyncEvent.POST,
                        result=result,
                        documents=documents,
                        primary_key=primary_key,
                    )
                    if isinstance(post["generic_result"], TaskInfo):
                        result = post["generic_result"]
                return result

            async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
                for plugin in self._concurrent_add_documents_plugins:
                    if _plugin_has_method(plugin, "run_plugin"):
                        tg.create_task(
                            plugin.run_plugin(  # type: ignore[union-attr]
                                event=AsyncEvent.CONCURRENT,
                                documents=documents,
                                primary_key=primary_key,
                            )
                        )
                    if _plugin_has_method(plugin, "run_document_plugin"):
                        tg.create_task(
                            plugin.run_document_plugin(  # type: ignore[union-attr]
                                event=AsyncEvent.CONCURRENT,
                                documents=documents,
                                primary_key=primary_key,
                            )
                        )

                response_coroutine = tg.create_task(
                    self._http_requests.post(url, documents, compress=compress)
                )

            response = await response_coroutine
            result = TaskInfo(**response.json())
            if self._post_add_documents_plugins:
                post = await AsyncIndex._run_plugins(
                    self._post_add_documents_plugins,
                    AsyncEvent.POST,
                    result=result,
                    documents=documents,
                    primary_key=primary_key,
                )
                if isinstance(post["generic_result"], TaskInfo):
                    result = post["generic_result"]

            return result

        response = await self._http_requests.post(url, documents, compress=compress)

        result = TaskInfo(**response.json())
        if self._post_add_documents_plugins:
            post = await AsyncIndex._run_plugins(
                self._post_add_documents_plugins,
                AsyncEvent.POST,
                result=result,
                documents=documents,
                primary_key=primary_key,
            )
            if isinstance(post["generic_result"], TaskInfo):
                result = post["generic_result"]

        return result

    async def add_documents_in_batches(
        self,
        documents: Sequence[JsonMapping],
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
        compress: bool = False,
        concurrency_limit: int | None = None,
    ) -> list[TaskInfo]:
        """Adds documents in batches to reduce RAM usage with indexing.

        Args:
            documents: List of documents.
            batch_size: The number of documents that should be included in each batch.
                Defaults to 1000.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            compress: If set to True the data will be sent in gzip format. Defaults to False.
            concurrency_limit: If set this will limit the number of batches that will be sent
                concurrently. This can be helpful if you find you are overloading the Meilisearch
                server with requests. Defaults to None.

        Returns:
            List of update ids to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> >>> documents = [
            >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
            >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
            >>> ]
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.add_documents_in_batches(documents)
        """
        if concurrency_limit:
            async with asyncio.Semaphore(concurrency_limit):
                if not use_task_groups():
                    batches = [
                        self.add_documents(x, primary_key, compress=compress)
                        for x in _batch(documents, batch_size)
                    ]
                    return await asyncio.gather(*batches)

                async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
                    tasks = [
                        tg.create_task(self.add_documents(x, primary_key, compress=compress))
                        for x in _batch(documents, batch_size)
                    ]

                return [x.result() for x in tasks]

        if not use_task_groups():
            batches = [
                self.add_documents(x, primary_key, compress=compress)
                for x in _batch(documents, batch_size)
            ]
            return await asyncio.gather(*batches)

        async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
            tasks = [
                tg.create_task(self.add_documents(x, primary_key, compress=compress))
                for x in _batch(documents, batch_size)
            ]

        return [x.result() for x in tasks]

    async def add_documents_from_directory(
        self,
        directory_path: Path | str,
        *,
        primary_key: str | None = None,
        document_type: str = "json",
        csv_delimiter: str | None = None,
        combine_documents: bool = True,
        compress: bool = False,
        concurrency_limit: int | None = None,
    ) -> list[TaskInfo]:
        """Load all json files from a directory and add the documents to the index.

        Args:
            directory_path: Path to the directory that contains the json files.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            document_type: The type of document being added. Accepted types are json, csv, and
                ndjson. For csv files the first row of the document should be a header row contining
                the field names, and ever for should have a title.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            combine_documents: If set to True this will combine the documents from all the files
                before indexing them. Defaults to True.
            compress: If set to True the data will be sent in gzip format. Defaults to False.
            concurrency_limit: If set this will limit the number of batches that will be sent
                concurrently. This can be helpful if you find you are overloading the Meilisearch
                server with requests. Defaults to None.

        Returns:
            The details of the task status.

        Raises:
            InvalidDocumentError: If the docucment is not a valid format for Meilisearch.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import AsyncClient
            >>> directory_path = Path("/path/to/directory/containing/files")
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.add_documents_from_directory(directory_path)
        """
        directory = Path(directory_path) if isinstance(directory_path, str) else directory_path

        if combine_documents:
            all_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await _async_load_documents_from_file(
                        path, csv_delimiter, json_handler=self._json_handler
                    )
                    all_documents.append(documents)

            _raise_on_no_documents(all_documents, document_type, directory_path)

            loop = asyncio.get_running_loop()
            combined = await loop.run_in_executor(None, partial(_combine_documents, all_documents))

            response = await self.add_documents(combined, primary_key, compress=compress)

            return [response]

        if concurrency_limit:
            async with asyncio.Semaphore(concurrency_limit):
                if not use_task_groups():
                    add_documents = []
                    for path in directory.iterdir():
                        if path.suffix == f".{document_type}":
                            documents = await _async_load_documents_from_file(
                                path, csv_delimiter, json_handler=self._json_handler
                            )
                            add_documents.append(
                                self.add_documents(documents, primary_key, compress=compress)
                            )

                    _raise_on_no_documents(add_documents, document_type, directory_path)

                    if len(add_documents) > 1:
                        # Send the first document on its own before starting the gather. Otherwise Meilisearch
                        # returns an error because it thinks all entries are trying to create the same index.
                        first_response = [await add_documents.pop()]

                        responses = await asyncio.gather(*add_documents)
                        responses = [*first_response, *responses]
                    else:
                        responses = [await add_documents[0]]

                    return responses

                async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
                    tasks = []
                    all_results = []
                    for i, path in enumerate(directory.iterdir()):
                        if path.suffix == f".{document_type}":
                            documents = await _async_load_documents_from_file(
                                path, csv_delimiter, json_handler=self._json_handler
                            )
                            if i == 0:
                                all_results = [
                                    await self.add_documents(documents, compress=compress)
                                ]
                            else:
                                tasks.append(
                                    tg.create_task(
                                        self.add_documents(
                                            documents, primary_key, compress=compress
                                        )
                                    )
                                )

        if not use_task_groups():
            add_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await _async_load_documents_from_file(
                        path, csv_delimiter, json_handler=self._json_handler
                    )
                    add_documents.append(
                        self.add_documents(documents, primary_key, compress=compress)
                    )

            _raise_on_no_documents(add_documents, document_type, directory_path)

            if len(add_documents) > 1:
                # Send the first document on its own before starting the gather. Otherwise Meilisearch
                # returns an error because it thinks all entries are trying to create the same index.
                first_response = [await add_documents.pop()]

                responses = await asyncio.gather(*add_documents)
                responses = [*first_response, *responses]
            else:
                responses = [await add_documents[0]]

            return responses

        async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
            tasks = []
            all_results = []
            for i, path in enumerate(directory.iterdir()):
                if path.suffix == f".{document_type}":
                    documents = await _async_load_documents_from_file(
                        path, csv_delimiter, json_handler=self._json_handler
                    )
                    if i == 0:
                        all_results = [await self.add_documents(documents, compress=compress)]
                    else:
                        tasks.append(
                            tg.create_task(
                                self.add_documents(documents, primary_key, compress=compress)
                            )
                        )

        results = [x.result() for x in tasks]
        all_results = [*all_results, *results]
        _raise_on_no_documents(all_results, document_type, directory_path)
        return all_results

    async def add_documents_from_directory_in_batches(
        self,
        directory_path: Path | str,
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
        document_type: str = "json",
        csv_delimiter: str | None = None,
        combine_documents: bool = True,
        compress: bool = False,
        concurrency_limit: int | None = None,
    ) -> list[TaskInfo]:
        """Load all json files from a directory and add the documents to the index in batches.

        Args:
            directory_path: Path to the directory that contains the json files.
            batch_size: The number of documents that should be included in each batch.
                Defaults to 1000.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            document_type: The type of document being added. Accepted types are json, csv, and
                ndjson. For csv files the first row of the document should be a header row contining
                the field names, and ever for should have a title.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            combine_documents: If set to True this will combine the documents from all the files
                before indexing them. Defaults to True.
            compress: If set to True the data will be sent in gzip format. Defaults to False.
            concurrency_limit: If set this will limit the number of batches that will be sent
                concurrently. This can be helpful if you find you are overloading the Meilisearch
                server with requests. Defaults to None.

        Returns:
            List of update ids to track the action.

        Raises:
            InvalidDocumentError: If the docucment is not a valid format for Meilisearch.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import AsyncClient
            >>> directory_path = Path("/path/to/directory/containing/files")
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.add_documents_from_directory_in_batches(directory_path)
        """
        directory = Path(directory_path) if isinstance(directory_path, str) else directory_path

        if combine_documents:
            all_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await _async_load_documents_from_file(
                        path, csv_delimiter=csv_delimiter, json_handler=self._json_handler
                    )
                    all_documents.append(documents)

            _raise_on_no_documents(all_documents, document_type, directory_path)

            loop = asyncio.get_running_loop()
            combined = await loop.run_in_executor(None, partial(_combine_documents, all_documents))

            return await self.add_documents_in_batches(
                combined,
                batch_size=batch_size,
                primary_key=primary_key,
                compress=compress,
                concurrency_limit=concurrency_limit,
            )

        responses: list[TaskInfo] = []

        add_documents = []
        for path in directory.iterdir():
            if path.suffix == f".{document_type}":
                documents = await _async_load_documents_from_file(
                    path, csv_delimiter, json_handler=self._json_handler
                )
                add_documents.append(
                    self.add_documents_in_batches(
                        documents,
                        batch_size=batch_size,
                        primary_key=primary_key,
                        compress=compress,
                        concurrency_limit=concurrency_limit,
                    )
                )

        _raise_on_no_documents(add_documents, document_type, directory_path)

        if len(add_documents) > 1:
            # Send the first document on its own before starting the gather. Otherwise Meilisearch
            # returns an error because it thinks all entries are trying to create the same index.
            first_response = await add_documents.pop()
            responses_gather = await asyncio.gather(*add_documents)
            responses = [*first_response, *[x for y in responses_gather for x in y]]
        else:
            responses = await add_documents[0]

        return responses

    async def add_documents_from_file(
        self,
        file_path: Path | str,
        primary_key: str | None = None,
        *,
        compress: bool = False,
    ) -> TaskInfo:
        """Add documents to the index from a json file.

        Args:
            file_path: Path to the json file.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            InvalidDocumentError: If the docucment is not a valid format for Meilisearch.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import AsyncClient
            >>> file_path = Path("/path/to/file.json")
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.add_documents_from_file(file_path)
        """
        documents = await _async_load_documents_from_file(
            file_path, json_handler=self._json_handler
        )

        return await self.add_documents(documents, primary_key=primary_key, compress=compress)

    async def add_documents_from_file_in_batches(
        self,
        file_path: Path | str,
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
        csv_delimiter: str | None = None,
        compress: bool = False,
        concurrency_limit: int | None = None,
    ) -> list[TaskInfo]:
        """Adds documents form a json file in batches to reduce RAM usage with indexing.

        Args:
            file_path: Path to the json file.
            batch_size: The number of documents that should be included in each batch.
                Defaults to 1000.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            compress: If set to True the data will be sent in gzip format. Defaults to False.
            concurrency_limit: If set this will limit the number of batches that will be sent
                concurrently. This can be helpful if you find you are overloading the Meilisearch
                server with requests. Defaults to None.

        Returns:
            List of update ids to track the action.

        Raises:
            InvalidDocumentError: If the docucment is not a valid format for Meilisearch.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import AsyncClient
            >>> file_path = Path("/path/to/file.json")
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.add_documents_from_file_in_batches(file_path)
        """
        documents = await _async_load_documents_from_file(
            file_path, csv_delimiter, json_handler=self._json_handler
        )

        return await self.add_documents_in_batches(
            documents,
            batch_size=batch_size,
            primary_key=primary_key,
            compress=compress,
            concurrency_limit=concurrency_limit,
        )

    async def add_documents_from_raw_file(
        self,
        file_path: Path | str,
        primary_key: str | None = None,
        *,
        csv_delimiter: str | None = None,
        compress: bool = False,
    ) -> TaskInfo:
        """Directly send csv or ndjson files to Meilisearch without pre-processing.

        The can reduce RAM usage from Meilisearch during indexing, but does not include the option
        for batching.

        Args:
            file_path: The path to the file to send to Meilisearch. Only csv and ndjson files are
                allowed.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task.

        Raises:
            ValueError: If the file is not a csv or ndjson file, or if a csv_delimiter is sent for
                a non-csv file.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import AsyncClient
            >>> file_path = Path("/path/to/file.csv")
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.add_documents_from_raw_file(file_path)
        """
        upload_path = Path(file_path) if isinstance(file_path, str) else file_path
        if not upload_path.exists():
            raise MeilisearchError("No file found at the specified path")

        if upload_path.suffix not in (".csv", ".ndjson"):
            raise ValueError("Only csv and ndjson files can be sent as binary files")

        if csv_delimiter and upload_path.suffix != ".csv":
            raise ValueError("A csv_delimiter can only be used with csv files")

        if (
            csv_delimiter
            and len(csv_delimiter) != 1
            or csv_delimiter
            and not csv_delimiter.isascii()
        ):
            raise ValueError("csv_delimiter must be a single ascii character")

        content_type = "text/csv" if upload_path.suffix == ".csv" else "application/x-ndjson"
        parameters = {}

        if primary_key:
            parameters["primaryKey"] = primary_key
        if csv_delimiter:
            parameters["csvDelimiter"] = csv_delimiter

        if parameters:
            url = _build_encoded_url(self._documents_url, parameters)
        else:
            url = self._documents_url

        async with aiofiles.open(upload_path) as f:
            data = await f.read()

        response = await self._http_requests.post(
            url, body=data, content_type=content_type, compress=compress
        )

        return TaskInfo(**response.json())

    async def edit_documents(
        self, function: str, *, context: JsonDict | None = None, filter: str | None = None
    ) -> TaskInfo:
        """Edit documents with a function.

        Edit documents is only available in Meilisearch >= v1.10.0, and is experimental in
        Meilisearch v1.10.0. In order to use this feature you first need to enable it by
        sending a PATCH request to /experimental-features with { "editDocumentsByFunction": true }.

        Args:
            function: Rhai function to use to update the documents.
            context: Parameters to use in the function. Defaults to None.
            filter: Filter the documents before applying the function. Defaults to None.

        Returns:
            The details of the task.

        Raises:
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.edit_documents("doc.title = `${doc.title.to_upper()}`")
        """
        url = f"{self._documents_url}/edit"
        payload: JsonDict = {"function": function}

        if context:
            payload["context"] = context

        if filter:
            payload["filter"] = filter

        response = await self._http_requests.post(url, payload)

        return TaskInfo(**response.json())

    async def update_documents(
        self,
        documents: Sequence[JsonMapping],
        primary_key: str | None = None,
        *,
        compress: bool = False,
    ) -> TaskInfo:
        """Update documents in the index.

        Args:
            documents: List of documents.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> documents = [
            >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
            >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
            >>> ]
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_documents(documents)
        """
        if primary_key:
            url = _build_encoded_url(self._documents_url, {"primaryKey": primary_key})
        else:
            url = self._documents_url

        if self._pre_update_documents_plugins:
            pre = await AsyncIndex._run_plugins(
                self._pre_update_documents_plugins,
                AsyncEvent.PRE,
                documents=documents,
                primary_key=primary_key,
            )
            if pre.get("document_result"):
                documents = pre["document_result"]

        if self._concurrent_update_documents_plugins:
            if not use_task_groups():
                tasks: Any = []
                for plugin in self._concurrent_update_documents_plugins:
                    if _plugin_has_method(plugin, "run_plugin"):
                        tasks.append(
                            plugin.run_plugin(  # type: ignore[union-attr]
                                event=AsyncEvent.CONCURRENT,
                                documents=documents,
                                primary_key=primary_key,
                            )
                        )
                    if _plugin_has_method(plugin, "run_document_plugin"):
                        tasks.append(
                            plugin.run_document_plugin(  # type: ignore[union-attr]
                                event=AsyncEvent.CONCURRENT,
                                documents=documents,
                                primary_key=primary_key,
                            )
                        )

                tasks.append(self._http_requests.put(url, documents, compress=compress))

                responses = await asyncio.gather(*tasks)
                result = TaskInfo(**responses[-1].json())
                if self._post_update_documents_plugins:
                    post = await AsyncIndex._run_plugins(
                        self._post_update_documents_plugins,
                        AsyncEvent.POST,
                        result=result,
                        documents=documents,
                        primary_key=primary_key,
                    )
                    if isinstance(post["generic_result"], TaskInfo):
                        result = post["generic_result"]

                return result

            async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
                for plugin in self._concurrent_update_documents_plugins:
                    if _plugin_has_method(plugin, "run_plugin"):
                        tg.create_task(
                            plugin.run_plugin(  # type: ignore[union-attr]
                                event=AsyncEvent.CONCURRENT,
                                documents=documents,
                                primary_key=primary_key,
                            )
                        )
                    if _plugin_has_method(plugin, "run_document_plugin"):
                        tg.create_task(
                            plugin.run_document_plugin(  # type: ignore[union-attr]
                                event=AsyncEvent.CONCURRENT,
                                documents=documents,
                                primary_key=primary_key,
                            )
                        )

                response_coroutine = tg.create_task(
                    self._http_requests.put(url, documents, compress=compress)
                )

            response = await response_coroutine
            result = TaskInfo(**response.json())
            if self._post_update_documents_plugins:
                post = await AsyncIndex._run_plugins(
                    self._post_update_documents_plugins,
                    AsyncEvent.POST,
                    result=result,
                    documents=documents,
                    primary_key=primary_key,
                )

                if isinstance(post["generic_result"], TaskInfo):
                    result = post["generic_result"]

            return result

        response = await self._http_requests.put(url, documents, compress=compress)
        result = TaskInfo(**response.json())
        if self._post_update_documents_plugins:
            post = await AsyncIndex._run_plugins(
                self._post_update_documents_plugins,
                AsyncEvent.POST,
                result=result,
                documents=documents,
                primary_key=primary_key,
            )
            if isinstance(post["generic_result"], TaskInfo):
                result = post["generic_result"]

        return result

    async def update_documents_in_batches(
        self,
        documents: Sequence[JsonMapping],
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
        compress: bool = False,
        concurrency_limit: int | None = None,
    ) -> list[TaskInfo]:
        """Update documents in batches to reduce RAM usage with indexing.

        Each batch tries to fill the max_payload_size

        Args:
            documents: List of documents.
            batch_size: The number of documents that should be included in each batch.
                Defaults to 1000.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            compress: If set to True the data will be sent in gzip format. Defaults to False.
            concurrency_limit: If set this will limit the number of batches that will be sent
                concurrently. This can be helpful if you find you are overloading the Meilisearch
                server with requests. Defaults to None.

        Returns:
            List of update ids to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> documents = [
            >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
            >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
            >>> ]
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_documents_in_batches(documents)
        """
        if concurrency_limit:
            async with asyncio.Semaphore(concurrency_limit):
                if not use_task_groups():
                    batches = [
                        self.update_documents(x, primary_key, compress=compress)
                        for x in _batch(documents, batch_size)
                    ]
                    return await asyncio.gather(*batches)

                async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
                    tasks = [
                        tg.create_task(self.update_documents(x, primary_key, compress=compress))
                        for x in _batch(documents, batch_size)
                    ]
                return [x.result() for x in tasks]

        if not use_task_groups():
            batches = [
                self.update_documents(x, primary_key, compress=compress)
                for x in _batch(documents, batch_size)
            ]
            return await asyncio.gather(*batches)

        async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
            tasks = [
                tg.create_task(self.update_documents(x, primary_key, compress=compress))
                for x in _batch(documents, batch_size)
            ]
        return [x.result() for x in tasks]

    async def update_documents_from_directory(
        self,
        directory_path: Path | str,
        *,
        primary_key: str | None = None,
        document_type: str = "json",
        csv_delimiter: str | None = None,
        combine_documents: bool = True,
        compress: bool = False,
    ) -> list[TaskInfo]:
        """Load all json files from a directory and update the documents.

        Args:
            directory_path: Path to the directory that contains the json files.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            document_type: The type of document being added. Accepted types are json, csv, and
                ndjson. For csv files the first row of the document should be a header row contining
                the field names, and ever for should have a title.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            combine_documents: If set to True this will combine the documents from all the files
                before indexing them. Defaults to True.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            InvalidDocumentError: If the docucment is not a valid format for Meilisearch.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import AsyncClient
            >>> directory_path = Path("/path/to/directory/containing/files")
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_documents_from_directory(directory_path)
        """
        directory = Path(directory_path) if isinstance(directory_path, str) else directory_path

        if combine_documents:
            all_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await _async_load_documents_from_file(
                        path, csv_delimiter, json_handler=self._json_handler
                    )
                    all_documents.append(documents)

            _raise_on_no_documents(all_documents, document_type, directory_path)

            loop = asyncio.get_running_loop()
            combined = await loop.run_in_executor(None, partial(_combine_documents, all_documents))

            response = await self.update_documents(combined, primary_key, compress=compress)
            return [response]

        if not use_task_groups():
            update_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await _async_load_documents_from_file(
                        path, csv_delimiter, json_handler=self._json_handler
                    )
                    update_documents.append(
                        self.update_documents(documents, primary_key, compress=compress)
                    )

            _raise_on_no_documents(update_documents, document_type, directory_path)

            if len(update_documents) > 1:
                # Send the first document on its own before starting the gather. Otherwise Meilisearch
                # returns an error because it thinks all entries are trying to create the same index.
                first_response = [await update_documents.pop()]
                responses = await asyncio.gather(*update_documents)
                responses = [*first_response, *responses]
            else:
                responses = [await update_documents[0]]

            return responses

        async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
            tasks = []
            results = []
            for i, path in enumerate(directory.iterdir()):
                if path.suffix == f".{document_type}":
                    documents = await _async_load_documents_from_file(
                        path, csv_delimiter, json_handler=self._json_handler
                    )
                    if i == 0:
                        results = [
                            await self.update_documents(documents, primary_key, compress=compress)
                        ]
                    else:
                        tasks.append(
                            tg.create_task(
                                self.update_documents(documents, primary_key, compress=compress)
                            )
                        )

        results = [*results, *[x.result() for x in tasks]]
        _raise_on_no_documents(results, document_type, directory_path)
        return results

    async def update_documents_from_directory_in_batches(
        self,
        directory_path: Path | str,
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
        document_type: str = "json",
        csv_delimiter: str | None = None,
        combine_documents: bool = True,
        compress: bool = False,
        concurrency_limit: int | None = None,
    ) -> list[TaskInfo]:
        """Load all json files from a directory and update the documents.

        Args:
            directory_path: Path to the directory that contains the json files.
            batch_size: The number of documents that should be included in each batch.
                Defaults to 1000.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            document_type: The type of document being added. Accepted types are json, csv, and
                ndjson. For csv files the first row of the document should be a header row contining
                the field names, and ever for should have a title.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            combine_documents: If set to True this will combine the documents from all the files
                before indexing them. Defaults to True.
            compress: If set to True the data will be sent in gzip format. Defaults to False.
            concurrency_limit: If set this will limit the number of batches that will be sent
                concurrently. This can be helpful if you find you are overloading the Meilisearch
                server with requests. Defaults to None.

        Returns:
            List of update ids to track the action.

        Raises:
            InvalidDocumentError: If the docucment is not a valid format for Meilisearch.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import AsyncClient
            >>> directory_path = Path("/path/to/directory/containing/files")
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_documents_from_directory_in_batches(directory_path)
        """
        directory = Path(directory_path) if isinstance(directory_path, str) else directory_path

        if combine_documents:
            all_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await _async_load_documents_from_file(
                        path, csv_delimiter, json_handler=self._json_handler
                    )
                    all_documents.append(documents)

            _raise_on_no_documents(all_documents, document_type, directory_path)

            loop = asyncio.get_running_loop()
            combined = await loop.run_in_executor(None, partial(_combine_documents, all_documents))

            return await self.update_documents_in_batches(
                combined,
                batch_size=batch_size,
                primary_key=primary_key,
                compress=compress,
                concurrency_limit=concurrency_limit,
            )

        if not use_task_groups():
            responses: list[TaskInfo] = []

            update_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await _async_load_documents_from_file(
                        path, csv_delimiter, json_handler=self._json_handler
                    )
                    update_documents.append(
                        self.update_documents_in_batches(
                            documents,
                            batch_size=batch_size,
                            primary_key=primary_key,
                            compress=compress,
                            concurrency_limit=concurrency_limit,
                        )
                    )

            _raise_on_no_documents(update_documents, document_type, directory_path)

            if len(update_documents) > 1:
                # Send the first document on its own before starting the gather. Otherwise Meilisearch
                # returns an error because it thinks all entries are trying to create the same index.
                first_response = await update_documents.pop()
                responses_gather = await asyncio.gather(*update_documents)
                responses = [*first_response, *[x for y in responses_gather for x in y]]
            else:
                responses = await update_documents[0]

            return responses

        async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
            results = []
            tasks = []
            for i, path in enumerate(directory.iterdir()):
                if path.suffix == f".{document_type}":
                    documents = await _async_load_documents_from_file(
                        path, csv_delimiter, json_handler=self._json_handler
                    )
                    if i == 0:
                        results = await self.update_documents_in_batches(
                            documents,
                            batch_size=batch_size,
                            primary_key=primary_key,
                            compress=compress,
                            concurrency_limit=concurrency_limit,
                        )
                    else:
                        tasks.append(
                            tg.create_task(
                                self.update_documents_in_batches(
                                    documents,
                                    batch_size=batch_size,
                                    primary_key=primary_key,
                                    compress=compress,
                                    concurrency_limit=concurrency_limit,
                                )
                            )
                        )

        results = [*results, *[x for y in tasks for x in y.result()]]
        _raise_on_no_documents(results, document_type, directory_path)
        return results

    async def update_documents_from_file(
        self,
        file_path: Path | str,
        primary_key: str | None = None,
        csv_delimiter: str | None = None,
        *,
        compress: bool = False,
    ) -> TaskInfo:
        """Add documents in the index from a json file.

        Args:
            file_path: Path to the json file.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import AsyncClient
            >>> file_path = Path("/path/to/file.json")
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_documents_from_file(file_path)
        """
        documents = await _async_load_documents_from_file(
            file_path, csv_delimiter, json_handler=self._json_handler
        )

        return await self.update_documents(documents, primary_key=primary_key, compress=compress)

    async def update_documents_from_file_in_batches(
        self,
        file_path: Path | str,
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
        compress: bool = False,
        concurrency_limit: int | None = None,
    ) -> list[TaskInfo]:
        """Updates documents form a json file in batches to reduce RAM usage with indexing.

        Args:
            file_path: Path to the json file.
            batch_size: The number of documents that should be included in each batch.
                Defaults to 1000.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            compress: If set to True the data will be sent in gzip format. Defaults to False.
            concurrency_limit: If set this will limit the number of batches that will be sent
                concurrently. This can be helpful if you find you are overloading the Meilisearch
                server with requests. Defaults to None.

        Returns:
            List of update ids to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import AsyncClient
            >>> file_path = Path("/path/to/file.json")
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_documents_from_file_in_batches(file_path)
        """
        documents = await _async_load_documents_from_file(
            file_path, json_handler=self._json_handler
        )

        return await self.update_documents_in_batches(
            documents,
            batch_size=batch_size,
            primary_key=primary_key,
            compress=compress,
            concurrency_limit=concurrency_limit,
        )

    async def update_documents_from_raw_file(
        self,
        file_path: Path | str,
        primary_key: str | None = None,
        csv_delimiter: str | None = None,
        *,
        compress: bool = False,
    ) -> TaskInfo:
        """Directly send csv or ndjson files to Meilisearch without pre-processing.

        The can reduce RAM usage from Meilisearch during indexing, but does not include the option
        for batching.

        Args:
            file_path: The path to the file to send to Meilisearch. Only csv and ndjson files are
                allowed.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            ValueError: If the file is not a csv or ndjson file, or if a csv_delimiter is sent for
                a non-csv file.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import AsyncClient
            >>> file_path = Path("/path/to/file.csv")
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_documents_from_raw_file(file_path)
        """
        upload_path = Path(file_path) if isinstance(file_path, str) else file_path
        if not upload_path.exists():
            raise MeilisearchError("No file found at the specified path")

        if upload_path.suffix not in (".csv", ".ndjson"):
            raise ValueError("Only csv and ndjson files can be sent as binary files")

        if csv_delimiter and upload_path.suffix != ".csv":
            raise ValueError("A csv_delimiter can only be used with csv files")

        if (
            csv_delimiter
            and len(csv_delimiter) != 1
            or csv_delimiter
            and not csv_delimiter.isascii()
        ):
            raise ValueError("csv_delimiter must be a single ascii character")

        content_type = "text/csv" if upload_path.suffix == ".csv" else "application/x-ndjson"
        parameters = {}

        if primary_key:
            parameters["primaryKey"] = primary_key
        if csv_delimiter:
            parameters["csvDelimiter"] = csv_delimiter

        if parameters:
            url = _build_encoded_url(self._documents_url, parameters)
        else:
            url = self._documents_url

        async with aiofiles.open(upload_path) as f:
            data = await f.read()

        response = await self._http_requests.put(
            url, body=data, content_type=content_type, compress=compress
        )

        return TaskInfo(**response.json())

    async def delete_document(self, document_id: str) -> TaskInfo:
        """Delete one document from the index.

        Args:
            document_id: Unique identifier of the document.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.delete_document("1234")
        """
        url = f"{self._documents_url}/{document_id}"

        if self._pre_delete_document_plugins:
            await AsyncIndex._run_plugins(
                self._pre_delete_document_plugins, AsyncEvent.PRE, document_id=document_id
            )

        if self._concurrent_delete_document_plugins:
            if not use_task_groups():
                tasks: Any = []
                for plugin in self._concurrent_delete_document_plugins:
                    tasks.append(
                        plugin.run_plugin(event=AsyncEvent.CONCURRENT, document_id=document_id)
                    )

                tasks.append(self._http_requests.delete(url))

                responses = await asyncio.gather(*tasks)
                result = TaskInfo(**responses[-1].json())
                if self._post_delete_document_plugins:
                    post = await AsyncIndex._run_plugins(
                        self._post_delete_document_plugins, AsyncEvent.POST, result=result
                    )
                    if isinstance(post.get("generic_result"), TaskInfo):
                        result = post["generic_result"]
                return result

            async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
                for plugin in self._concurrent_delete_document_plugins:
                    tg.create_task(
                        plugin.run_plugin(event=AsyncEvent.CONCURRENT, document_id=document_id)
                    )

                response_coroutine = tg.create_task(self._http_requests.delete(url))

            response = await response_coroutine
            result = TaskInfo(**response.json())
            if self._post_delete_document_plugins:
                post = await AsyncIndex._run_plugins(
                    self._post_delete_document_plugins, event=AsyncEvent.POST, result=result
                )
                if isinstance(post["generic_result"], TaskInfo):
                    result = post["generic_result"]
            return result

        response = await self._http_requests.delete(url)
        result = TaskInfo(**response.json())
        if self._post_delete_document_plugins:
            post = await AsyncIndex._run_plugins(
                self._post_delete_document_plugins, AsyncEvent.POST, result=result
            )
            if isinstance(post["generic_result"], TaskInfo):
                result = post["generic_result"]

        return result

    async def delete_documents(self, ids: list[str]) -> TaskInfo:
        """Delete multiple documents from the index.

        Args:
            ids: List of unique identifiers of documents.

        Returns:
            List of update ids to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.delete_documents(["1234", "5678"])
        """
        url = f"{self._documents_url}/delete-batch"

        if self._pre_delete_documents_plugins:
            await AsyncIndex._run_plugins(
                self._pre_delete_documents_plugins, AsyncEvent.PRE, ids=ids
            )

        if self._concurrent_delete_documents_plugins:
            if not use_task_groups():
                tasks: Any = []
                for plugin in self._concurrent_delete_documents_plugins:
                    tasks.append(plugin.run_plugin(event=AsyncEvent.CONCURRENT, ids=ids))

                tasks.append(self._http_requests.post(url, ids))

                responses = await asyncio.gather(*tasks)
                result = TaskInfo(**responses[-1].json())
                if self._post_delete_documents_plugins:
                    post = await AsyncIndex._run_plugins(
                        self._post_delete_documents_plugins, AsyncEvent.POST, result=result
                    )
                    if isinstance(post.get("generic_result"), TaskInfo):
                        result = post["generic_result"]
                return result

            async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
                for plugin in self._concurrent_delete_documents_plugins:
                    tg.create_task(plugin.run_plugin(event=AsyncEvent.CONCURRENT, ids=ids))

                response_coroutine = tg.create_task(self._http_requests.post(url, ids))

            response = await response_coroutine
            result = TaskInfo(**response.json())
            if self._post_delete_documents_plugins:
                post = await AsyncIndex._run_plugins(
                    self._post_delete_documents_plugins, AsyncEvent.POST, result=result
                )
                if isinstance(post["generic_result"], TaskInfo):
                    result = post["generic_result"]
            return result

        response = await self._http_requests.post(url, ids)
        result = TaskInfo(**response.json())
        if self._post_delete_documents_plugins:
            post = await AsyncIndex._run_plugins(
                self._post_delete_documents_plugins, AsyncEvent.POST, result=result
            )
            if isinstance(post["generic_result"], TaskInfo):
                result = post["generic_result"]

        return result

    async def delete_documents_by_filter(self, filter: Filter) -> TaskInfo:
        """Delete documents from the index by filter.

        Args:
            filter: The filter value information.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_pyrhon_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.delete_documents_by_filter("genre=horor"))
        """
        url = f"{self._documents_url}/delete"

        if self._pre_delete_documents_by_filter_plugins:
            await AsyncIndex._run_plugins(
                self._pre_delete_documents_by_filter_plugins, AsyncEvent.PRE, filter=filter
            )

        if self._concurrent_delete_documents_by_filter_plugins:
            if not use_task_groups():
                tasks: Any = []
                for plugin in self._concurrent_delete_documents_by_filter_plugins:
                    tasks.append(plugin.run_plugin(event=AsyncEvent.CONCURRENT, filter=filter))

                tasks.append(self._http_requests.post(url, body={"filter": filter}))

                responses = await asyncio.gather(*tasks)
                result = TaskInfo(**responses[-1].json())
                if self._post_delete_documents_by_filter_plugins:
                    post = await AsyncIndex._run_plugins(
                        self._post_delete_documents_by_filter_plugins,
                        AsyncEvent.POST,
                        result=result,
                    )
                    if isinstance(post["generic_result"], TaskInfo):
                        result = post["generic_result"]
                return result

            async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
                for plugin in self._concurrent_delete_documents_by_filter_plugins:
                    tg.create_task(plugin.run_plugin(event=AsyncEvent.CONCURRENT, filter=filter))

                response_coroutine = tg.create_task(
                    self._http_requests.post(url, body={"filter": filter})
                )

            response = await response_coroutine
            result = TaskInfo(**response.json())
            if self._post_delete_documents_by_filter_plugins:
                post = await AsyncIndex._run_plugins(
                    self._post_delete_documents_by_filter_plugins, AsyncEvent.POST, result=result
                )
                if isinstance(post["generic_result"], TaskInfo):
                    result = post["generic_result"]

            return result

        response = await self._http_requests.post(url, body={"filter": filter})
        result = TaskInfo(**response.json())
        if self._post_delete_documents_by_filter_plugins:
            post = await AsyncIndex._run_plugins(
                self._post_delete_documents_by_filter_plugins, AsyncEvent.POST, result=result
            )
            if isinstance(post.get("generic_result"), TaskInfo):
                result = post["generic_result"]
        return result

    async def delete_documents_in_batches_by_filter(
        self, filters: list[str | list[str | list[str]]], concurrency_limit: int | None = None
    ) -> list[TaskInfo]:
        """Delete batches of documents from the index by filter.

        Args:
            filters: A list of filter value information.
            concurrency_limit: If set this will limit the number of batches that will be sent
                concurrently. This can be helpful if you find you are overloading the Meilisearch
                server with requests. Defaults to None.

        Returns:
            The a list of details of the task statuses.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.delete_documents_in_batches_by_filter(
            >>>         [
            >>>             "genre=horor"),
            >>>             "release_date=1520035200"),
            >>>         ]
            >>>     )
        """
        if concurrency_limit:
            async with asyncio.Semaphore(concurrency_limit):
                if not use_task_groups():
                    tasks = [self.delete_documents_by_filter(filter) for filter in filters]
                    return await asyncio.gather(*tasks)

                async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
                    tg_tasks = [
                        tg.create_task(self.delete_documents_by_filter(filter))
                        for filter in filters
                    ]

                return [x.result() for x in tg_tasks]

        if not use_task_groups():
            tasks = [self.delete_documents_by_filter(filter) for filter in filters]
            return await asyncio.gather(*tasks)

        async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
            tg_tasks = [
                tg.create_task(self.delete_documents_by_filter(filter)) for filter in filters
            ]

        return [x.result() for x in tg_tasks]

    async def delete_all_documents(self) -> TaskInfo:
        """Delete all documents from the index.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.delete_all_document()
        """
        if self._pre_delete_all_documents_plugins:
            await AsyncIndex._run_plugins(self._pre_delete_all_documents_plugins, AsyncEvent.PRE)

        if self._concurrent_delete_all_documents_plugins:
            if not use_task_groups():
                tasks: Any = []
                for plugin in self._concurrent_delete_all_documents_plugins:
                    tasks.append(plugin.run_plugin(event=AsyncEvent.CONCURRENT))

                tasks.append(self._http_requests.delete(self._documents_url))

                responses = await asyncio.gather(*tasks)
                result = TaskInfo(**responses[-1].json())
                if self._post_delete_all_documents_plugins:
                    post = await AsyncIndex._run_plugins(
                        self._post_delete_all_documents_plugins, AsyncEvent.POST, result=result
                    )
                    if isinstance(post.get("generic_result"), TaskInfo):
                        result = post["generic_result"]
                return result

            async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
                for plugin in self._concurrent_delete_all_documents_plugins:
                    tg.create_task(plugin.run_plugin(event=AsyncEvent.CONCURRENT))

                response_coroutine = tg.create_task(self._http_requests.delete(self._documents_url))

            response = await response_coroutine
            result = TaskInfo(**response.json())
            if self._post_delete_all_documents_plugins:
                post = await AsyncIndex._run_plugins(
                    self._post_delete_all_documents_plugins, AsyncEvent.POST, result=result
                )
                if isinstance(post.get("generic_result"), TaskInfo):
                    result = post["generic_result"]
            return result

        response = await self._http_requests.delete(self._documents_url)
        result = TaskInfo(**response.json())
        if self._post_delete_all_documents_plugins:
            post = await AsyncIndex._run_plugins(
                self._post_delete_all_documents_plugins, AsyncEvent.POST, result=result
            )
            if isinstance(post.get("generic_result"), TaskInfo):
                result = post["generic_result"]
        return result

    async def get_settings(self) -> MeilisearchSettings:
        """Get settings of the index.

        Returns:
            Settings of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     settings = await index.get_settings()
        """
        response = await self._http_requests.get(self._settings_url)
        response_json = response.json()
        settings = MeilisearchSettings(**response_json)

        if response_json.get("embedders"):
            # TODO: Add back after embedder setting issue fixed https://github.com/meilisearch/meilisearch/issues/4585
            settings.embedders = _embedder_json_to_settings_model(  # pragma: no cover
                response_json["embedders"]
            )

        return settings

    async def update_settings(
        self, body: MeilisearchSettings, *, compress: bool = False
    ) -> TaskInfo:
        """Update settings of the index.

        Args:
            body: Settings of the index.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> from meilisearch_python_sdk import MeilisearchSettings
            >>> new_settings = MeilisearchSettings(
            >>>     synonyms={"wolverine": ["xmen", "logan"], "logan": ["wolverine"]},
            >>>     stop_words=["the", "a", "an"],
            >>>     ranking_rules=[
            >>>         "words",
            >>>         "typo",
            >>>         "proximity",
            >>>         "attribute",
            >>>         "sort",
            >>>         "exactness",
            >>>         "release_date:desc",
            >>>         "rank:desc",
            >>>    ],
            >>>    filterable_attributes=["genre", "director"],
            >>>    distinct_attribute="url",
            >>>    searchable_attributes=["title", "description", "genre"],
            >>>    displayed_attributes=["title", "description", "genre", "release_date"],
            >>>    sortable_attributes=["title", "release_date"],
            >>> )
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_settings(new_settings)
        """
        body_dict = {
            k: v
            for k, v in body.model_dump(by_alias=True, exclude_none=True).items()
            if v is not None
        }
        response = await self._http_requests.patch(self._settings_url, body_dict, compress=compress)

        return TaskInfo(**response.json())

    async def reset_settings(self) -> TaskInfo:
        """Reset settings of the index to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_settings()
        """
        response = await self._http_requests.delete(self._settings_url)

        return TaskInfo(**response.json())

    async def get_ranking_rules(self) -> list[str]:
        """Get ranking rules of the index.

        Returns:
            List containing the ranking rules of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     ranking_rules = await index.get_ranking_rules()
        """
        response = await self._http_requests.get(f"{self._settings_url}/ranking-rules")

        return response.json()

    async def update_ranking_rules(
        self, ranking_rules: list[str], *, compress: bool = False
    ) -> TaskInfo:
        """Update ranking rules of the index.

        Args:
            ranking_rules: List containing the ranking rules.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> ranking_rules=[
            >>>      "words",
            >>>      "typo",
            >>>      "proximity",
            >>>      "attribute",
            >>>      "sort",
            >>>      "exactness",
            >>>      "release_date:desc",
            >>>      "rank:desc",
            >>> ],
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_ranking_rules(ranking_rules)
        """
        response = await self._http_requests.put(
            f"{self._settings_url}/ranking-rules", ranking_rules, compress=compress
        )

        return TaskInfo(**response.json())

    async def reset_ranking_rules(self) -> TaskInfo:
        """Reset ranking rules of the index to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_ranking_rules()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/ranking-rules")

        return TaskInfo(**response.json())

    async def get_distinct_attribute(self) -> str | None:
        """Get distinct attribute of the index.

        Returns:
            String containing the distinct attribute of the index. If no distinct attribute
                `None` is returned.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     distinct_attribute = await index.get_distinct_attribute()
        """
        response = await self._http_requests.get(f"{self._settings_url}/distinct-attribute")

        if not response.json():
            return None

        return response.json()

    async def update_distinct_attribute(self, body: str, *, compress: bool = False) -> TaskInfo:
        """Update distinct attribute of the index.

        Args:
            body: Distinct attribute.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_distinct_attribute("url")
        """
        response = await self._http_requests.put(
            f"{self._settings_url}/distinct-attribute", body, compress=compress
        )

        return TaskInfo(**response.json())

    async def reset_distinct_attribute(self) -> TaskInfo:
        """Reset distinct attribute of the index to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_distinct_attributes()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/distinct-attribute")

        return TaskInfo(**response.json())

    async def get_searchable_attributes(self) -> list[str]:
        """Get searchable attributes of the index.

        Returns:
            List containing the searchable attributes of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     searchable_attributes = await index.get_searchable_attributes()
        """
        response = await self._http_requests.get(f"{self._settings_url}/searchable-attributes")

        return response.json()

    async def update_searchable_attributes(
        self, body: list[str], *, compress: bool = False
    ) -> TaskInfo:
        """Update searchable attributes of the index.

        Args:
            body: List containing the searchable attributes.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_searchable_attributes(["title", "description", "genre"])
        """
        response = await self._http_requests.put(
            f"{self._settings_url}/searchable-attributes", body, compress=compress
        )

        return TaskInfo(**response.json())

    async def reset_searchable_attributes(self) -> TaskInfo:
        """Reset searchable attributes of the index to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_searchable_attributes()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/searchable-attributes")

        return TaskInfo(**response.json())

    async def get_displayed_attributes(self) -> list[str]:
        """Get displayed attributes of the index.

        Returns:
            List containing the displayed attributes of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     displayed_attributes = await index.get_displayed_attributes()
        """
        response = await self._http_requests.get(f"{self._settings_url}/displayed-attributes")

        return response.json()

    async def update_displayed_attributes(
        self, body: list[str], *, compress: bool = False
    ) -> TaskInfo:
        """Update displayed attributes of the index.

        Args:
            body: List containing the displayed attributes.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_displayed_attributes(
            >>>         ["title", "description", "genre", "release_date"]
            >>>     )
        """
        response = await self._http_requests.put(
            f"{self._settings_url}/displayed-attributes", body, compress=compress
        )

        return TaskInfo(**response.json())

    async def reset_displayed_attributes(self) -> TaskInfo:
        """Reset displayed attributes of the index to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_displayed_attributes()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/displayed-attributes")

        return TaskInfo(**response.json())

    async def get_stop_words(self) -> list[str] | None:
        """Get stop words of the index.

        Returns:
            List containing the stop words of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     stop_words = await index.get_stop_words()
        """
        response = await self._http_requests.get(f"{self._settings_url}/stop-words")

        if not response.json():
            return None

        return response.json()

    async def update_stop_words(self, body: list[str], *, compress: bool = False) -> TaskInfo:
        """Update stop words of the index.

        Args:
            body: List containing the stop words of the index.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_stop_words(["the", "a", "an"])
        """
        response = await self._http_requests.put(
            f"{self._settings_url}/stop-words", body, compress=compress
        )

        return TaskInfo(**response.json())

    async def reset_stop_words(self) -> TaskInfo:
        """Reset stop words of the index to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_stop_words()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/stop-words")

        return TaskInfo(**response.json())

    async def get_synonyms(self) -> dict[str, list[str]] | None:
        """Get synonyms of the index.

        Returns:
            The synonyms of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     synonyms = await index.get_synonyms()
        """
        response = await self._http_requests.get(f"{self._settings_url}/synonyms")

        if not response.json():
            return None

        return response.json()

    async def update_synonyms(
        self, body: dict[str, list[str]], *, compress: bool = False
    ) -> TaskInfo:
        """Update synonyms of the index.

        Args:
            body: The synonyms of the index.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_synonyms(
            >>>         {"wolverine": ["xmen", "logan"], "logan": ["wolverine"]}
            >>>     )
        """
        response = await self._http_requests.put(
            f"{self._settings_url}/synonyms", body, compress=compress
        )

        return TaskInfo(**response.json())

    async def reset_synonyms(self) -> TaskInfo:
        """Reset synonyms of the index to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_synonyms()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/synonyms")

        return TaskInfo(**response.json())

    async def get_filterable_attributes(self) -> list[str] | list[FilterableAttributes] | None:
        """Get filterable attributes of the index.

        Returns:
            Filterable attributes of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     filterable_attributes = await index.get_filterable_attributes()
        """
        response = await self._http_requests.get(f"{self._settings_url}/filterable-attributes")

        if not response.json():
            return None

        response_json = response.json()

        if isinstance(response_json[0], str):
            return response_json

        filterable_attributes = []
        for r in response_json:
            filterable_attributes.append(
                FilterableAttributes(
                    attribute_patterns=r["attributePatterns"],
                    features=FilterableAttributeFeatures(**r["features"]),
                )
            )

        return filterable_attributes

    async def update_filterable_attributes(
        self, body: list[str] | list[FilterableAttributes], *, compress: bool = False
    ) -> TaskInfo:
        """Update filterable attributes of the index.

        Args:
            body: List containing the filterable attributes of the index.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_filterable_attributes(["genre", "director"])
        """
        payload: list[str | JsonDict] = []

        for b in body:
            if isinstance(b, FilterableAttributes):
                payload.append(b.model_dump(by_alias=True))
            else:
                payload.append(b)

        response = await self._http_requests.put(
            f"{self._settings_url}/filterable-attributes", payload, compress=compress
        )

        return TaskInfo(**response.json())

    async def reset_filterable_attributes(self) -> TaskInfo:
        """Reset filterable attributes of the index to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_filterable_attributes()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/filterable-attributes")

        return TaskInfo(**response.json())

    async def get_sortable_attributes(self) -> list[str]:
        """Get sortable attributes of the AsyncIndex.

        Returns:
            List containing the sortable attributes of the AsyncIndex.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     sortable_attributes = await index.get_sortable_attributes()
        """
        response = await self._http_requests.get(f"{self._settings_url}/sortable-attributes")

        return response.json()

    async def update_sortable_attributes(
        self, sortable_attributes: list[str], *, compress: bool = False
    ) -> TaskInfo:
        """Get sortable attributes of the AsyncIndex.

        Args:
            sortable_attributes: List of attributes for searching.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_sortable_attributes(["title", "release_date"])
        """
        response = await self._http_requests.put(
            f"{self._settings_url}/sortable-attributes", sortable_attributes, compress=compress
        )

        return TaskInfo(**response.json())

    async def reset_sortable_attributes(self) -> TaskInfo:
        """Reset sortable attributes of the index to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_sortable_attributes()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/sortable-attributes")

        return TaskInfo(**response.json())

    async def get_typo_tolerance(self) -> TypoTolerance:
        """Get typo tolerance for the index.

        Returns:
            TypoTolerance for the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     sortable_attributes = await index.get_typo_tolerance()
        """
        response = await self._http_requests.get(f"{self._settings_url}/typo-tolerance")

        return TypoTolerance(**response.json())

    async def update_typo_tolerance(
        self, typo_tolerance: TypoTolerance, *, compress: bool = False
    ) -> TaskInfo:
        """Update typo tolerance.

        Args:
            typo_tolerance: Typo tolerance settings.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     TypoTolerance(enabled=False)
            >>>     await index.update_typo_tolerance()
        """
        response = await self._http_requests.patch(
            f"{self._settings_url}/typo-tolerance",
            typo_tolerance.model_dump(by_alias=True, exclude_unset=True),
            compress=compress,
        )

        return TaskInfo(**response.json())

    async def reset_typo_tolerance(self) -> TaskInfo:
        """Reset typo tolerance to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_typo_tolerance()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/typo-tolerance")

        return TaskInfo(**response.json())

    async def get_faceting(self) -> Faceting:
        """Get faceting for the index.

        Returns:
            Faceting for the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     faceting = await index.get_faceting()
        """
        response = await self._http_requests.get(f"{self._settings_url}/faceting")

        return Faceting(**response.json())

    async def update_faceting(self, faceting: Faceting, *, compress: bool = False) -> TaskInfo:
        """Partially update the faceting settings for an index.

        Args:
            faceting: Faceting values.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_faceting(faceting=Faceting(max_values_per_facet=100))
        """
        response = await self._http_requests.patch(
            f"{self._settings_url}/faceting",
            faceting.model_dump(by_alias=True),
            compress=compress,
        )

        return TaskInfo(**response.json())

    async def reset_faceting(self) -> TaskInfo:
        """Reset an index's faceting settings to their default value.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_faceting()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/faceting")

        return TaskInfo(**response.json())

    async def get_pagination(self) -> Pagination:
        """Get pagination settings for the index.

        Returns:
            Pagination for the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     pagination_settings = await index.get_pagination()
        """
        response = await self._http_requests.get(f"{self._settings_url}/pagination")

        return Pagination(**response.json())

    async def update_pagination(self, settings: Pagination, *, compress: bool = False) -> TaskInfo:
        """Partially update the pagination settings for an index.

        Args:
            settings: settings for pagination.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> from meilisearch_python_sdk.models.settings import Pagination
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_pagination(settings=Pagination(max_total_hits=123))
        """
        response = await self._http_requests.patch(
            f"{self._settings_url}/pagination",
            settings.model_dump(by_alias=True),
            compress=compress,
        )

        return TaskInfo(**response.json())

    async def reset_pagination(self) -> TaskInfo:
        """Reset an index's pagination settings to their default value.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_pagination()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/pagination")

        return TaskInfo(**response.json())

    async def get_separator_tokens(self) -> list[str]:
        """Get separator token settings for the index.

        Returns:
            Separator tokens for the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     separator_token_settings = await index.get_separator_tokens()
        """
        response = await self._http_requests.get(f"{self._settings_url}/separator-tokens")

        return response.json()

    async def update_separator_tokens(
        self, separator_tokens: list[str], *, compress: bool = False
    ) -> TaskInfo:
        """Update the separator tokens settings for an index.

        Args:
            separator_tokens: List of separator tokens.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_separator_tokens(separator_tokenes=["|", "/")
        """
        response = await self._http_requests.put(
            f"{self._settings_url}/separator-tokens", separator_tokens, compress=compress
        )

        return TaskInfo(**response.json())

    async def reset_separator_tokens(self) -> TaskInfo:
        """Reset an index's separator tokens settings to the default value.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_separator_tokens()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/separator-tokens")

        return TaskInfo(**response.json())

    async def get_non_separator_tokens(self) -> list[str]:
        """Get non-separator token settings for the index.

        Returns:
            Non-separator tokens for the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     non_separator_token_settings = await index.get_non_separator_tokens()
        """
        response = await self._http_requests.get(f"{self._settings_url}/non-separator-tokens")

        return response.json()

    async def update_non_separator_tokens(
        self, non_separator_tokens: list[str], *, compress: bool = False
    ) -> TaskInfo:
        """Update the non-separator tokens settings for an index.

        Args:
            non_separator_tokens: List of non-separator tokens.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_non_separator_tokens(non_separator_tokens=["@", "#")
        """
        response = await self._http_requests.put(
            f"{self._settings_url}/non-separator-tokens", non_separator_tokens, compress=compress
        )

        return TaskInfo(**response.json())

    async def reset_non_separator_tokens(self) -> TaskInfo:
        """Reset an index's non-separator tokens settings to the default value.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_non_separator_tokens()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/non-separator-tokens")

        return TaskInfo(**response.json())

    async def get_search_cutoff_ms(self) -> int | None:
        """Get search cutoff time in ms.

        Returns:
            Integer representing the search cutoff time in ms, or None.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     search_cutoff_ms_settings = await index.get_search_cutoff_ms()
        """
        response = await self._http_requests.get(f"{self._settings_url}/search-cutoff-ms")

        return response.json()

    async def update_search_cutoff_ms(
        self, search_cutoff_ms: int, *, compress: bool = False
    ) -> TaskInfo:
        """Update the search cutoff for an index.

        Args:
            search_cutoff_ms: Integer value of the search cutoff time in ms.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_search_cutoff_ms(100)
        """
        response = await self._http_requests.put(
            f"{self._settings_url}/search-cutoff-ms", search_cutoff_ms, compress=compress
        )

        return TaskInfo(**response.json())

    async def reset_search_cutoff_ms(self) -> TaskInfo:
        """Reset the search cutoff time to the default value.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_search_cutoff_ms()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/search-cutoff-ms")

        return TaskInfo(**response.json())

    async def get_word_dictionary(self) -> list[str]:
        """Get word dictionary settings for the index.

        Returns:
            Word dictionary for the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     word_dictionary = await index.get_word_dictionary()
        """
        response = await self._http_requests.get(f"{self._settings_url}/dictionary")

        return response.json()

    async def update_word_dictionary(
        self, dictionary: list[str], *, compress: bool = False
    ) -> TaskInfo:
        """Update the word dictionary settings for an index.

        Args:
            dictionary: List of dictionary values.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_word_dictionary(dictionary=["S.O.S", "S.O")
        """
        response = await self._http_requests.put(
            f"{self._settings_url}/dictionary", dictionary, compress=compress
        )

        return TaskInfo(**response.json())

    async def reset_word_dictionary(self) -> TaskInfo:
        """Reset an index's word dictionary settings to the default value.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_word_dictionary()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/dictionary")

        return TaskInfo(**response.json())

    async def get_proximity_precision(self) -> ProximityPrecision:
        """Get proximity precision settings for the index.

        Returns:
            Proximity precision for the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     proximity_precision = await index.get_proximity_precision()
        """
        response = await self._http_requests.get(f"{self._settings_url}/proximity-precision")

        return ProximityPrecision[to_snake(response.json()).upper()]

    async def update_proximity_precision(
        self, proximity_precision: ProximityPrecision, *, compress: bool = False
    ) -> TaskInfo:
        """Update the proximity precision settings for an index.

        Args:
            proximity_precision: The proximity precision value.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> from meilisearch_python_sdk.models.settings import ProximityPrecision
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_proximity_precision(ProximityPrecision.BY_ATTRIBUTE)
        """
        response = await self._http_requests.put(
            f"{self._settings_url}/proximity-precision",
            proximity_precision.value,
            compress=compress,
        )

        return TaskInfo(**response.json())

    async def reset_proximity_precision(self) -> TaskInfo:
        """Reset an index's proximity precision settings to the default value.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_proximity_precision()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/proximity-precision")

        return TaskInfo(**response.json())

    async def get_embedders(self) -> Embedders | None:
        """Get embedder settings for the index.

        Returns:
            Embedders for the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     embedders = await index.get_embedders()
        """
        response = await self._http_requests.get(f"{self._settings_url}/embedders")

        return _embedder_json_to_embedders_model(response.json())

    async def update_embedders(self, embedders: Embedders, *, compress: bool = False) -> TaskInfo:
        """Update the embedders settings for an index.

        Args:
            embedders: The embedders value.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> from meilisearch_python_sdk.models.settings import Embedders, UserProvidedEmbedder
            >>>
            >>>
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_embedders(
            >>>         Embedders(embedders={"default": UserProvidedEmbedder(dimensions=512)})
            >>>     )
        """
        payload = {}
        for key, embedder in embedders.embedders.items():
            payload[key] = {
                k: v
                for k, v in embedder.model_dump(by_alias=True, exclude_none=True).items()
                if v is not None
            }

        response = await self._http_requests.patch(
            f"{self._settings_url}/embedders", payload, compress=compress
        )

        return TaskInfo(**response.json())

    async def reset_embedders(self) -> TaskInfo:
        """Reset an index's embedders settings to the default value.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_embedders()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/embedders")

        return TaskInfo(**response.json())

    async def get_localized_attributes(self) -> list[LocalizedAttributes] | None:
        """Get localized attributes settings for the index.

        Returns:
            Localized attributes for the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     localized_attributes = await index.get_localized_attributes()
        """
        response = await self._http_requests.get(f"{self._settings_url}/localized-attributes")

        if not response.json():
            return None

        return [LocalizedAttributes(**x) for x in response.json()]

    async def update_localized_attributes(
        self, localized_attributes: list[LocalizedAttributes], *, compress: bool = False
    ) -> TaskInfo:
        """Update the localized attributes settings for an index.

        Args:
            localized_attributes: The localized attributes value.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> from meilisearch_python_sdk.models.settings import LocalizedAttributes
            >>>
            >>>
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_localized_attributes([
            >>>         LocalizedAttributes(locales=["eng", "spa"], attribute_patterns=["*"]),
            >>>         LocalizedAttributes(locales=["ita"], attribute_patterns=["*_it"]),
            >>>     ])
        """
        payload = [x.model_dump(by_alias=True) for x in localized_attributes]
        response = await self._http_requests.put(
            f"{self._settings_url}/localized-attributes", payload, compress=compress
        )

        return TaskInfo(**response.json())

    async def reset_localized_attributes(self) -> TaskInfo:
        """Reset an index's localized attributes settings to the default value.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_localized_attributes()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/localized-attributes")

        return TaskInfo(**response.json())

    async def get_facet_search(self) -> bool | None:
        """Get setting for facet search opt-out.

        Returns:
            True if facet search is enabled or False if not.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     facet_search = await index.get_facet_search()
        """
        response = await self._http_requests.get(f"{self._settings_url}/facet-search")

        return response.json()

    async def update_facet_search(self, facet_search: bool, *, compress: bool = False) -> TaskInfo:
        """Update setting for facet search opt-out.

        Args:
            facet_search: Boolean indicating if facet search should be disabled.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_facet_search(True)
        """
        response = await self._http_requests.put(
            f"{self._settings_url}/facet-search",
            facet_search,
            compress=compress,
        )

        return TaskInfo(**response.json())

    async def reset_facet_search(self) -> TaskInfo:
        """Reset the facet search opt-out settings.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_facet_search()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/facet-search")

        return TaskInfo(**response.json())

    async def get_prefix_search(self) -> str:
        """Get setting for prefix search opt-out.

        Returns:
            True if prefix search is enabled or False if not.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = await client.index("movies")
            >>>     prefix_search = await index.get_prefix_search()
        """
        response = await self._http_requests.get(f"{self._settings_url}/prefix-search")

        return response.json()

    async def update_prefix_search(
        self,
        prefix_search: Literal["disabled", "indexingTime", "searchTime"],
        *,
        compress: bool = False,
    ) -> TaskInfo:
        """Update setting for prefix search opt-out.

        Args:
            prefix_search: Value indicating prefix search setting.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = await client.index("movies")
            >>>     await index.update_prefix_search("disabled")
        """
        response = await self._http_requests.put(
            f"{self._settings_url}/prefix-search",
            prefix_search,
            compress=compress,
        )

        return TaskInfo(**response.json())

    async def reset_prefix_search(self) -> TaskInfo:
        """Reset the prefix search opt-out settings.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     index = await client.index("movies")
            >>>     await index.reset_prefix_search()
        """
        response = await self._http_requests.delete(f"{self._settings_url}/prefix-search")

        return TaskInfo(**response.json())

    @staticmethod
    async def _run_plugins(
        plugins: Sequence[AsyncPlugin | AsyncDocumentPlugin | AsyncPostSearchPlugin],
        event: AsyncEvent,
        **kwargs: Any,
    ) -> dict[str, Any]:
        generic_plugins = []
        document_plugins = []
        search_plugins = []
        results: dict[str, Any] = {
            "generic_result": None,
            "document_result": None,
            "search_result": None,
        }
        if not use_task_groups():
            for plugin in plugins:
                if _plugin_has_method(plugin, "run_plugin"):
                    generic_plugins.append(plugin.run_plugin(event=event, **kwargs))  # type: ignore[union-attr]
                if _plugin_has_method(plugin, "run_document_plugin"):
                    document_plugins.append(plugin.run_document_plugin(event=event, **kwargs))  # type: ignore[union-attr]
                if _plugin_has_method(plugin, "run_post_search_plugin"):
                    search_plugins.append(plugin.run_post_search_plugin(event=event, **kwargs))  # type: ignore[union-attr]
            if generic_plugins:
                generic_results = await asyncio.gather(*generic_plugins)
                if generic_results:
                    results["generic_result"] = generic_results[-1]

            if document_plugins:
                document_results = await asyncio.gather(*document_plugins)
                if document_results:
                    results["document_result"] = document_results[-1]
            if search_plugins:
                search_results = await asyncio.gather(*search_plugins)
                if search_results:
                    results["search_result"] = search_results[-1]

            return results

        async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
            generic_tasks = []
            document_tasks = []
            search_tasks = []
            for plugin in plugins:
                if _plugin_has_method(plugin, "run_plugin"):
                    generic_tasks.append(tg.create_task(plugin.run_plugin(event=event, **kwargs)))  # type: ignore[union-attr]
                if _plugin_has_method(plugin, "run_document_plugin"):
                    document_tasks.append(
                        tg.create_task(plugin.run_document_plugin(event=event, **kwargs))  # type: ignore[union-attr]
                    )
                if _plugin_has_method(plugin, "run_post_search_plugin"):
                    search_tasks.append(
                        tg.create_task(plugin.run_post_search_plugin(event=event, **kwargs))  # type: ignore[union-attr]
                    )

        if generic_tasks:
            for result in reversed(generic_tasks):
                if result:
                    results["generic_result"] = await result
                    break

        if document_tasks:
            results["document_result"] = await document_tasks[-1]

        if search_tasks:
            results["search_result"] = await search_tasks[-1]

        return results


class Index(_BaseIndex):
    """Index class gives access to all indexes routes and child routes.

    https://docs.meilisearch.com/reference/api/indexes.html
    """

    def __init__(
        self,
        http_client: Client,
        uid: str,
        primary_key: str | None = None,
        created_at: str | datetime | None = None,
        updated_at: str | datetime | None = None,
        plugins: IndexPlugins | None = None,
        json_handler: BuiltinHandler | OrjsonHandler | UjsonHandler | None = None,
        *,
        hits_type: Any = JsonDict,
    ):
        """Class initializer.

        Args:
            http_client: An instance of the Client. This automatically gets passed by the
                Client when creating and Index instance.
            uid: The index's unique identifier.
            primary_key: The primary key of the documents. Defaults to None.
            created_at: The date and time the index was created. Defaults to None.
            updated_at: The date and time the index was last updated. Defaults to None.
            plugins: Optional plugins can be provided to extend functionality.
            json_handler: The module to use for json operations. The options are BuiltinHandler
                (uses the json module from the standard library), OrjsonHandler (uses orjson), or
                UjsonHandler (uses ujson). Note that in order use orjson or ujson the corresponding
                extra needs to be included. Default: BuiltinHandler.
            hits_type: Allows for a custom type to be passed to use for hits. Defaults to
                JsonDict
        """
        super().__init__(
            uid=uid,
            primary_key=primary_key,
            created_at=created_at,
            updated_at=updated_at,
            json_handler=json_handler,
            hits_type=hits_type,
        )
        self.http_client = http_client
        self._http_requests = HttpRequests(http_client, json_handler=self._json_handler)
        self.plugins = plugins

    @cached_property
    def _post_add_documents_plugins(self) -> list[Plugin | DocumentPlugin] | None:
        if not self.plugins or not self.plugins.add_documents_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.add_documents_plugins if plugin.POST_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _pre_add_documents_plugins(self) -> list[Plugin | DocumentPlugin] | None:
        if not self.plugins or not self.plugins.add_documents_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.add_documents_plugins if plugin.PRE_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _post_delete_all_documents_plugins(self) -> list[Plugin] | None:
        if not self.plugins or not self.plugins.delete_all_documents_plugins:
            return None

        plugins = [
            plugin for plugin in self.plugins.delete_all_documents_plugins if plugin.POST_EVENT
        ]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _pre_delete_all_documents_plugins(self) -> list[Plugin] | None:
        if not self.plugins or not self.plugins.delete_all_documents_plugins:
            return None

        plugins = [
            plugin for plugin in self.plugins.delete_all_documents_plugins if plugin.PRE_EVENT
        ]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _post_delete_document_plugins(self) -> list[Plugin] | None:
        if not self.plugins or not self.plugins.delete_document_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.delete_document_plugins if plugin.POST_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _pre_delete_document_plugins(self) -> list[Plugin] | None:
        if not self.plugins or not self.plugins.delete_document_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.delete_document_plugins if plugin.PRE_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _post_delete_documents_plugins(self) -> list[Plugin] | None:
        if not self.plugins or not self.plugins.delete_documents_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.delete_documents_plugins if plugin.POST_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _pre_delete_documents_plugins(self) -> list[Plugin] | None:
        if not self.plugins or not self.plugins.delete_documents_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.delete_documents_plugins if plugin.PRE_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _post_delete_documents_by_filter_plugins(self) -> list[Plugin] | None:
        if not self.plugins or not self.plugins.delete_documents_by_filter_plugins:
            return None

        plugins = [
            plugin
            for plugin in self.plugins.delete_documents_by_filter_plugins
            if plugin.POST_EVENT
        ]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _pre_delete_documents_by_filter_plugins(self) -> list[Plugin] | None:
        if not self.plugins or not self.plugins.delete_documents_by_filter_plugins:
            return None

        plugins = [
            plugin for plugin in self.plugins.delete_documents_by_filter_plugins if plugin.PRE_EVENT
        ]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _post_facet_search_plugins(self) -> list[Plugin] | None:
        if not self.plugins or not self.plugins.facet_search_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.facet_search_plugins if plugin.POST_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _pre_facet_search_plugins(self) -> list[Plugin] | None:
        if not self.plugins or not self.plugins.facet_search_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.facet_search_plugins if plugin.PRE_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _post_search_plugins(self) -> list[Plugin | PostSearchPlugin] | None:
        if not self.plugins or not self.plugins.search_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.search_plugins if plugin.POST_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _pre_search_plugins(self) -> list[Plugin | PostSearchPlugin] | None:
        if not self.plugins or not self.plugins.search_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.search_plugins if plugin.PRE_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _post_update_documents_plugins(self) -> list[Plugin | DocumentPlugin] | None:
        if not self.plugins or not self.plugins.update_documents_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.update_documents_plugins if plugin.POST_EVENT]

        if not plugins:
            return None

        return plugins

    @cached_property
    def _pre_update_documents_plugins(self) -> list[Plugin | DocumentPlugin] | None:
        if not self.plugins or not self.plugins.update_documents_plugins:
            return None

        plugins = [plugin for plugin in self.plugins.update_documents_plugins if plugin.PRE_EVENT]

        if not plugins:
            return None

        return plugins

    def delete(self) -> TaskInfo:
        """Deletes the index.

        Returns:
            The details of the task.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.delete()
        """
        response = self._http_requests.delete(self._base_url_with_uid)
        return TaskInfo(**response.json())

    def delete_if_exists(self) -> bool:
        """Delete the index if it already exists.

        Returns:
            True if the index was deleted or False if not.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.delete_if_exists()
        """
        response = self.delete()
        status = wait_for_task(self.http_client, response.task_uid, timeout_in_ms=100000)
        if status.status == "succeeded":
            return True

        return False

    def update(self, primary_key: str) -> Self:
        """Update the index primary key.

        Args:
            primary_key: The primary key of the documents.

        Returns:
            An instance of the AsyncIndex with the updated information.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> updated_index = index.update()
        """
        payload = {"primaryKey": primary_key}
        response = self._http_requests.patch(self._base_url_with_uid, payload)
        wait_for_task(self.http_client, response.json()["taskUid"], timeout_in_ms=100000)
        index_response = self._http_requests.get(self._base_url_with_uid)
        self.primary_key = index_response.json()["primaryKey"]
        return self

    def fetch_info(self) -> Self:
        """Gets the infromation about the index.

        Returns:
            An instance of the AsyncIndex containing the retrieved information.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index_info = index.fetch_info()
        """
        response = self._http_requests.get(self._base_url_with_uid)
        index_dict = response.json()
        self._set_fetch_info(
            index_dict["primaryKey"], index_dict["createdAt"], index_dict["updatedAt"]
        )
        return self

    def get_primary_key(self) -> str | None:
        """Get the primary key.

        Returns:
            The primary key for the documents in the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> primary_key = index.get_primary_key()
        """
        info = self.fetch_info()
        return info.primary_key

    @classmethod
    def create(
        cls,
        http_client: Client,
        uid: str,
        primary_key: str | None = None,
        *,
        settings: MeilisearchSettings | None = None,
        wait: bool = True,
        timeout_in_ms: int | None = None,
        plugins: IndexPlugins | None = None,
        json_handler: BuiltinHandler | OrjsonHandler | UjsonHandler | None = None,
        hits_type: Any = JsonDict,
    ) -> Self:
        """Creates a new index.

        In general this method should not be used directly and instead the index should be created
        through the `Client`.

        Args:
            http_client: An instance of the Client. This automatically gets passed by the Client
                when creating an Index instance.
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
            json_handler: The module to use for json operations. The options are BuiltinHandler
                (uses the json module from the standard library), OrjsonHandler (uses orjson), or
                UjsonHandler (uses ujson). Note that in order use orjson or ujson the corresponding
                extra needs to be included. Default: BuiltinHandler.
            hits_type: Allows for a custom type to be passed to use for hits. Defaults to
                JsonDict

        Returns:
            An instance of Index containing the information of the newly created index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = index.create(client, "movies")
        """
        if not primary_key:
            payload = {"uid": uid}
        else:
            payload = {"primaryKey": primary_key, "uid": uid}

        url = "indexes"
        handler = json_handler if json_handler else BuiltinHandler()
        http_request = HttpRequests(http_client, handler)
        response = http_request.post(url, payload)
        wait_for_task(http_client, response.json()["taskUid"], timeout_in_ms=timeout_in_ms)
        index_response = http_request.get(f"{url}/{uid}")
        index_dict = index_response.json()
        index = cls(
            http_client=http_client,
            uid=index_dict["uid"],
            primary_key=index_dict["primaryKey"],
            created_at=index_dict["createdAt"],
            updated_at=index_dict["updatedAt"],
            plugins=plugins,
            json_handler=json_handler,
            hits_type=hits_type,
        )

        if settings:
            settings_task = index.update_settings(settings)
            if wait:
                wait_for_task(http_client, settings_task.task_uid, timeout_in_ms=timeout_in_ms)

        return index

    def get_stats(self) -> IndexStats:
        """Get stats of the index.

        Returns:
            Stats of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> stats = index.get_stats()
        """
        response = self._http_requests.get(self._stats_url)

        return IndexStats(**response.json())

    def search(
        self,
        query: str | None = None,
        *,
        offset: int = 0,
        limit: int = 20,
        filter: Filter | None = None,
        facets: list[str] | None = None,
        attributes_to_retrieve: list[str] | None = None,
        attributes_to_crop: list[str] | None = None,
        crop_length: int = 200,
        attributes_to_highlight: list[str] | None = None,
        sort: list[str] | None = None,
        show_matches_position: bool = False,
        highlight_pre_tag: str = "<em>",
        highlight_post_tag: str = "</em>",
        crop_marker: str = "...",
        matching_strategy: Literal["all", "last", "frequency"] = "last",
        hits_per_page: int | None = None,
        page: int | None = None,
        attributes_to_search_on: list[str] | None = None,
        distinct: str | None = None,
        show_ranking_score: bool = False,
        show_ranking_score_details: bool = False,
        ranking_score_threshold: float | None = None,
        vector: list[float] | None = None,
        hybrid: Hybrid | None = None,
        locales: list[str] | None = None,
        retrieve_vectors: bool | None = None,
    ) -> SearchResults:
        """Search the index.

        Args:
            query: String containing the word(s) to search
            offset: Number of documents to skip. Defaults to 0.
            limit: Maximum number of documents returned. Defaults to 20.
            filter: Filter queries by an attribute value. Defaults to None.
            facets: Facets for which to retrieve the matching count. Defaults to None.
            attributes_to_retrieve: Attributes to display in the returned documents.
                Defaults to ["*"].
            attributes_to_crop: Attributes whose values have to be cropped. Defaults to None.
            crop_length: The maximun number of words to display. Defaults to 200.
            attributes_to_highlight: Attributes whose values will contain highlighted matching terms.
                Defaults to None.
            sort: Attributes by which to sort the results. Defaults to None.
            show_matches_position: Defines whether an object that contains information about the
                matches should be returned or not. Defaults to False.
            highlight_pre_tag: The opening tag for highlighting text. Defaults to <em>.
            highlight_post_tag: The closing tag for highlighting text. Defaults to </em>
            crop_marker: Marker to display when the number of words excedes the `crop_length`.
                Defaults to ...
            matching_strategy: Specifies the matching strategy Meilisearch should use. Defaults to
                `last`.
            hits_per_page: Sets the number of results returned per page.
            page: Sets the specific results page to fetch.
            attributes_to_search_on: List of field names. Allow search over a subset of searchable
                attributes without modifying the index settings. Defaults to None.
            distinct: If set the distinct value will return at most one result for the
                filterable attribute. Note that a filterable attributes must be set for this work.
                Defaults to None.
            show_ranking_score: If set to True the ranking score will be returned with each document
                in the search. Defaults to False.
            show_ranking_score_details: If set to True the ranking details will be returned with
                each document in the search. Defaults to False. Note: This parameter can only be
                used with Meilisearch >= v1.3.0, and is experimental in Meilisearch v1.3.0. In order
                to use this feature in Meilisearch v1.3.0 you first need to enable the feature by
                sending a PATCH request to /experimental-features with { "scoreDetails": true }.
                Because this feature is experimental it may be removed or updated causing breaking
                changes in this library without a major version bump so use with caution. This
                feature became stable in Meiliseach v1.7.0.
            ranking_score_threshold: If set, no document whose _rankingScore is under the
                rankingScoreThreshold is returned. The value must be between 0.0 and 1.0. Defaults
                to None.
            vector: List of vectors for vector search. Defaults to None. Note: This parameter can
                only be used with Meilisearch >= v1.3.0, and is experimental in Meilisearch v1.3.0.
                In order to use this feature in Meilisearch v1.3.0 you first need to enable the
                feature by sending a PATCH request to /experimental-features with
                { "vectorStore": true }. Because this feature is experimental it may be removed or
                updated causing breaking changes in this library without a major version bump so use
                with caution.
            hybrid: Hybrid search information. Defaults to None. Note: This parameter can
                only be used with Meilisearch >= v1.6.0, and is experimental in Meilisearch v1.6.0.
                In order to use this feature in Meilisearch v1.6.0 you first need to enable the
                feature by sending a PATCH request to /experimental-features with
                { "vectorStore": true }. Because this feature is experimental it may be removed or
                updated causing breaking changes in this library without a major version bump so use
                with caution.
            locales: Specifies the languages for the search. This parameter can only be used with
                Milisearch >= v1.10.0. Defaults to None letting the Meilisearch pick.
            retrieve_vectors: Return document vector data with search result.

        Returns:
            Results of the search

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> search_results = index.search("Tron")
        """
        if ranking_score_threshold:
            _validate_ranking_score_threshold(ranking_score_threshold)

        body = _process_search_parameters(
            q=query,
            offset=offset,
            limit=limit,
            filter=filter,
            facets=facets,
            attributes_to_retrieve=attributes_to_retrieve,
            attributes_to_crop=attributes_to_crop,
            crop_length=crop_length,
            attributes_to_highlight=attributes_to_highlight,
            sort=sort,
            show_matches_position=show_matches_position,
            highlight_pre_tag=highlight_pre_tag,
            highlight_post_tag=highlight_post_tag,
            crop_marker=crop_marker,
            matching_strategy=matching_strategy,
            hits_per_page=hits_per_page,
            page=page,
            attributes_to_search_on=attributes_to_search_on,
            distinct=distinct,
            show_ranking_score=show_ranking_score,
            show_ranking_score_details=show_ranking_score_details,
            vector=vector,
            hybrid=hybrid,
            ranking_score_threshold=ranking_score_threshold,
            locales=locales,
            retrieve_vectors=retrieve_vectors,
        )

        if self._pre_search_plugins:
            Index._run_plugins(
                self._pre_search_plugins,
                Event.PRE,
                query=query,
                offset=offset,
                limit=limit,
                filter=filter,
                facets=facets,
                attributes_to_retrieve=attributes_to_retrieve,
                attributes_to_crop=attributes_to_crop,
                crop_length=crop_length,
                attributes_to_highlight=attributes_to_highlight,
                sort=sort,
                show_matches_position=show_matches_position,
                highlight_pre_tag=highlight_pre_tag,
                highlight_post_tag=highlight_post_tag,
                crop_marker=crop_marker,
                matching_strategy=matching_strategy,
                hits_per_page=hits_per_page,
                page=page,
                attributes_to_search_on=attributes_to_search_on,
                distinct=distinct,
                show_ranking_score=show_ranking_score,
                show_ranking_score_details=show_ranking_score_details,
                vector=vector,
                hybrid=hybrid,
            )

        response = self._http_requests.post(f"{self._base_url_with_uid}/search", body=body)
        result = SearchResults[self.hits_type](**response.json())  # type: ignore[name-defined]
        if self._post_search_plugins:
            post = Index._run_plugins(self._post_search_plugins, Event.POST, search_results=result)
            if post.get("search_result"):
                result = post["search_result"]

        return result

    def facet_search(
        self,
        query: str | None = None,
        *,
        facet_name: str,
        facet_query: str,
        offset: int = 0,
        limit: int = 20,
        filter: Filter | None = None,
        facets: list[str] | None = None,
        attributes_to_retrieve: list[str] | None = None,
        attributes_to_crop: list[str] | None = None,
        crop_length: int = 200,
        attributes_to_highlight: list[str] | None = None,
        sort: list[str] | None = None,
        show_matches_position: bool = False,
        highlight_pre_tag: str = "<em>",
        highlight_post_tag: str = "</em>",
        crop_marker: str = "...",
        matching_strategy: Literal["all", "last", "frequency"] = "last",
        hits_per_page: int | None = None,
        page: int | None = None,
        attributes_to_search_on: list[str] | None = None,
        show_ranking_score: bool = False,
        show_ranking_score_details: bool = False,
        ranking_score_threshold: float | None = None,
        vector: list[float] | None = None,
        locales: list[str] | None = None,
        retrieve_vectors: bool | None = None,
        exhaustive_facet_count: bool | None = None,
    ) -> FacetSearchResults:
        """Search the index.

        Args:
            query: String containing the word(s) to search
            facet_name: The name of the facet to search
            facet_query: The facet search value
            offset: Number of documents to skip. Defaults to 0.
            limit: Maximum number of documents returned. Defaults to 20.
            filter: Filter queries by an attribute value. Defaults to None.
            facets: Facets for which to retrieve the matching count. Defaults to None.
            attributes_to_retrieve: Attributes to display in the returned documents.
                Defaults to ["*"].
            attributes_to_crop: Attributes whose values have to be cropped. Defaults to None.
            crop_length: The maximun number of words to display. Defaults to 200.
            attributes_to_highlight: Attributes whose values will contain highlighted matching terms.
                Defaults to None.
            sort: Attributes by which to sort the results. Defaults to None.
            show_matches_position: Defines whether an object that contains information about the
                matches should be returned or not. Defaults to False.
            highlight_pre_tag: The opening tag for highlighting text. Defaults to <em>.
            highlight_post_tag: The closing tag for highlighting text. Defaults to </em>
            crop_marker: Marker to display when the number of words excedes the `crop_length`.
                Defaults to ...
            matching_strategy: Specifies the matching strategy Meilisearch should use. Defaults to
                `last`.
            hits_per_page: Sets the number of results returned per page.
            page: Sets the specific results page to fetch.
            attributes_to_search_on: List of field names. Allow search over a subset of searchable
                attributes without modifying the index settings. Defaults to None.
            show_ranking_score: If set to True the ranking score will be returned with each document
                in the search. Defaults to False.
            show_ranking_score_details: If set to True the ranking details will be returned with
                each document in the search. Defaults to False. Note: This parameter can only be
                used with Meilisearch >= v1.3.0, and is experimental in Meilisearch v1.3.0. In order
                to use this feature in Meilisearch v1.3.0 you first need to enable the feature by
                sending a PATCH request to /experimental-features with { "scoreDetails": true }.
                Because this feature is experimental it may be removed or updated causing breaking
                changes in this library without a major version bump so use with caution. This
                feature became stable in Meiliseach v1.7.0.
            ranking_score_threshold: If set, no document whose _rankingScore is under the
                rankingScoreThreshold is returned. The value must be between 0.0 and 1.0. Defaults
                to None.
            vector: List of vectors for vector search. Defaults to None. Note: This parameter can
                only be used with Meilisearch >= v1.3.0, and is experimental in Meilisearch v1.3.0.
                In order to use this feature in Meilisearch v1.3.0 you first need to enable the
                feature by sending a PATCH request to /experimental-features with
                { "vectorStore": true }. Because this feature is experimental it may be removed or
                updated causing breaking changes in this library without a major version bump so use
                with caution.
            locales: Specifies the languages for the search. This parameter can only be used with
                Milisearch >= v1.10.0. Defaults to None letting the Meilisearch pick.
            retrieve_vectors: Return document vector data with search result.
            exhaustive_facet_count: forcing the facet search to compute the facet counts the same
                way as the paginated search. This parameter can only be used with Milisearch >=
                v1.14.0. Defaults to None.

        Returns:
            Results of the search

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> search_results = index.search(
            >>>     "Tron",
            >>>     facet_name="genre",
            >>>     facet_query="Sci-fi"
            >>> )
        """
        if ranking_score_threshold:
            _validate_ranking_score_threshold(ranking_score_threshold)

        body = _process_search_parameters(
            q=query,
            facet_name=facet_name,
            facet_query=facet_query,
            offset=offset,
            limit=limit,
            filter=filter,
            facets=facets,
            attributes_to_retrieve=attributes_to_retrieve,
            attributes_to_crop=attributes_to_crop,
            crop_length=crop_length,
            attributes_to_highlight=attributes_to_highlight,
            sort=sort,
            show_matches_position=show_matches_position,
            highlight_pre_tag=highlight_pre_tag,
            highlight_post_tag=highlight_post_tag,
            crop_marker=crop_marker,
            matching_strategy=matching_strategy,
            hits_per_page=hits_per_page,
            page=page,
            attributes_to_search_on=attributes_to_search_on,
            show_ranking_score=show_ranking_score,
            show_ranking_score_details=show_ranking_score_details,
            ranking_score_threshold=ranking_score_threshold,
            vector=vector,
            locales=locales,
            retrieve_vectors=retrieve_vectors,
            exhaustive_facet_count=exhaustive_facet_count,
        )

        if self._pre_facet_search_plugins:
            Index._run_plugins(
                self._pre_facet_search_plugins,
                Event.PRE,
                query=query,
                offset=offset,
                limit=limit,
                filter=filter,
                facets=facets,
                attributes_to_retrieve=attributes_to_retrieve,
                attributes_to_crop=attributes_to_crop,
                crop_length=crop_length,
                attributes_to_highlight=attributes_to_highlight,
                sort=sort,
                show_matches_position=show_matches_position,
                highlight_pre_tag=highlight_pre_tag,
                highlight_post_tag=highlight_post_tag,
                crop_marker=crop_marker,
                matching_strategy=matching_strategy,
                hits_per_page=hits_per_page,
                page=page,
                attributes_to_search_on=attributes_to_search_on,
                show_ranking_score=show_ranking_score,
                show_ranking_score_details=show_ranking_score_details,
                ranking_score_threshold=ranking_score_threshold,
                vector=vector,
                exhaustive_facet_count=exhaustive_facet_count,
            )

        response = self._http_requests.post(f"{self._base_url_with_uid}/facet-search", body=body)
        result = FacetSearchResults(**response.json())
        if self._post_facet_search_plugins:
            post = Index._run_plugins(self._post_facet_search_plugins, Event.POST, result=result)
            if isinstance(post["generic_result"], FacetSearchResults):
                result = post["generic_result"]

        return result

    def search_similar_documents(
        self,
        id: str,
        *,
        offset: int | None = None,
        limit: int | None = None,
        filter: str | None = None,
        embedder: str = "default",
        attributes_to_retrieve: list[str] | None = None,
        show_ranking_score: bool = False,
        show_ranking_score_details: bool = False,
        ranking_score_threshold: float | None = None,
    ) -> SimilarSearchResults:
        """Search the index.

        Args:
            id: The id for the target document that is being used to find similar documents.
            offset: Number of documents to skip. Defaults to 0.
            limit: Maximum number of documents returned. Defaults to 20.
            filter: Filter queries by an attribute value. Defaults to None.
            embedder: The vector DB to use for the search.
            attributes_to_retrieve: Attributes to display in the returned documents.
                Defaults to ["*"].
            show_ranking_score: If set to True the ranking score will be returned with each document
                in the search. Defaults to False.
            show_ranking_score_details: If set to True the ranking details will be returned with
                each document in the search. Defaults to False.
            ranking_score_threshold: If set, no document whose _rankingScore is under the
                rankingScoreThreshold is returned. The value must be between 0.0 and 1.0. Defaults
                to None.

        Returns:
            Results of the search

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> search_results = index.search_similar_documents("123")
        """
        payload = {
            "id": id,
            "filter": filter,
            "embedder": embedder,
            "attributesToRetrieve": attributes_to_retrieve,
            "showRankingScore": show_ranking_score,
            "showRankingScoreDetails": show_ranking_score_details,
            "rankingScoreThreshold": ranking_score_threshold,
        }

        if offset:
            payload["offset"] = offset

        if limit:
            payload["limit"] = limit

        response = self._http_requests.post(f"{self._base_url_with_uid}/similar", body=payload)

        return SimilarSearchResults[self.hits_type](**response.json())  # type: ignore[name-defined]

    def get_document(
        self,
        document_id: str,
        *,
        fields: list[str] | None = None,
        retrieve_vectors: bool = False,
    ) -> JsonDict:
        """Get one document with given document identifier.

        Args:
            document_id: Unique identifier of the document.
            fields: Document attributes to show. If this value is None then all
                attributes are retrieved. Defaults to None.
            retrieve_vectors: If set to True the embedding vectors will be returned with the document.
                Defaults to False. Note: This parameter can only be
                used with Meilisearch >= v1.13.0
        Returns:
            The document information

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> document = index.get_document("1234")
        """
        parameters: JsonDict = {}

        if fields:
            parameters["fields"] = ",".join(fields)
        if retrieve_vectors:
            parameters["retrieveVectors"] = "true"

        url = _build_encoded_url(f"{self._documents_url}/{document_id}", parameters)

        response = self._http_requests.get(url)
        return response.json()

    def get_documents(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        fields: list[str] | None = None,
        filter: Filter | None = None,
        retrieve_vectors: bool = False,
    ) -> DocumentsInfo:
        """Get a batch documents from the index.

        Args:
            offset: Number of documents to skip. Defaults to 0.
            limit: Maximum number of documents returnedd. Defaults to 20.
            fields: Document attributes to show. If this value is None then all
                attributes are retrieved. Defaults to None.
            filter: Filter value information. Defaults to None. Note: This parameter can only be
                used with Meilisearch >= v1.2.0
            retrieve_vectors: If set to True the vectors will be returned with each document.
                Defaults to False. Note: This parameter can only be
                used with Meilisearch >= v1.13.0

        Returns:
            Documents info.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.


        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> documents = index.get_documents()
        """
        parameters: JsonDict = {
            "offset": offset,
            "limit": limit,
        }

        if retrieve_vectors:
            parameters["retrieveVectors"] = "true"

        if not filter:
            if fields:
                parameters["fields"] = ",".join(fields)

            url = _build_encoded_url(self._documents_url, parameters)
            response = self._http_requests.get(url)

            return DocumentsInfo(**response.json())

        if fields:
            parameters["fields"] = fields

        parameters["filter"] = filter
        response = self._http_requests.post(f"{self._documents_url}/fetch", body=parameters)

        return DocumentsInfo(**response.json())

    def add_documents(
        self,
        documents: Sequence[JsonMapping],
        primary_key: str | None = None,
        *,
        compress: bool = False,
    ) -> TaskInfo:
        """Add documents to the index.

        Args:
            documents: List of documents.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> documents = [
            >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
            >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
            >>> ]
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.add_documents(documents)
        """
        if primary_key:
            url = _build_encoded_url(self._documents_url, {"primaryKey": primary_key})
        else:
            url = self._documents_url

        if self._pre_add_documents_plugins:
            pre = Index._run_plugins(
                self._pre_add_documents_plugins,
                Event.PRE,
                documents=documents,
                primary_key=primary_key,
            )
            if pre.get("document_result"):
                documents = pre["document_result"]

        response = self._http_requests.post(url, documents, compress=compress)
        result = TaskInfo(**response.json())
        if self._post_add_documents_plugins:
            post = Index._run_plugins(self._post_add_documents_plugins, Event.POST, result=result)
            if isinstance(post.get("generic_result"), TaskInfo):
                result = post["generic_result"]

        return result

    def add_documents_in_batches(
        self,
        documents: Sequence[JsonMapping],
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
        compress: bool = False,
    ) -> list[TaskInfo]:
        """Adds documents in batches to reduce RAM usage with indexing.

        Args:
            documents: List of documents.
            batch_size: The number of documents that should be included in each batch.
                Defaults to 1000.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            List of update ids to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> >>> documents = [
            >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
            >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
            >>> ]
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.add_documents_in_batches(documents)
        """
        return [
            self.add_documents(x, primary_key, compress=compress)
            for x in _batch(documents, batch_size)
        ]

    def add_documents_from_directory(
        self,
        directory_path: Path | str,
        *,
        primary_key: str | None = None,
        document_type: str = "json",
        csv_delimiter: str | None = None,
        combine_documents: bool = True,
        compress: bool = False,
    ) -> list[TaskInfo]:
        """Load all json files from a directory and add the documents to the index.

        Args:
            directory_path: Path to the directory that contains the json files.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            document_type: The type of document being added. Accepted types are json, csv, and
                ndjson. For csv files the first row of the document should be a header row contining
                the field names, and ever for should have a title.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            combine_documents: If set to True this will combine the documents from all the files
                before indexing them. Defaults to True.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            InvalidDocumentError: If the docucment is not a valid format for Meilisearch.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import Client
            >>> directory_path = Path("/path/to/directory/containing/files")
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.add_documents_from_directory(directory_path)
        """
        directory = Path(directory_path) if isinstance(directory_path, str) else directory_path

        if combine_documents:
            all_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = _load_documents_from_file(
                        path, csv_delimiter, json_handler=self._json_handler
                    )
                    all_documents.append(documents)

            _raise_on_no_documents(all_documents, document_type, directory_path)

            combined = _combine_documents(all_documents)

            response = self.add_documents(combined, primary_key, compress=compress)

            return [response]

        responses = []
        for path in directory.iterdir():
            if path.suffix == f".{document_type}":
                documents = _load_documents_from_file(
                    path, csv_delimiter, json_handler=self._json_handler
                )
                responses.append(self.add_documents(documents, primary_key, compress=compress))

        _raise_on_no_documents(responses, document_type, directory_path)

        return responses

    def add_documents_from_directory_in_batches(
        self,
        directory_path: Path | str,
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
        document_type: str = "json",
        csv_delimiter: str | None = None,
        combine_documents: bool = True,
        compress: bool = False,
    ) -> list[TaskInfo]:
        """Load all json files from a directory and add the documents to the index in batches.

        Args:
            directory_path: Path to the directory that contains the json files.
            batch_size: The number of documents that should be included in each batch.
                Defaults to 1000.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            document_type: The type of document being added. Accepted types are json, csv, and
                ndjson. For csv files the first row of the document should be a header row contining
                the field names, and ever for should have a title.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            combine_documents: If set to True this will combine the documents from all the files
                before indexing them. Defaults to True.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            List of update ids to track the action.

        Raises:
            InvalidDocumentError: If the docucment is not a valid format for Meilisearch.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import Client
            >>> directory_path = Path("/path/to/directory/containing/files")
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.add_documents_from_directory_in_batches(directory_path)
        """
        directory = Path(directory_path) if isinstance(directory_path, str) else directory_path

        if combine_documents:
            all_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = _load_documents_from_file(
                        path, csv_delimiter=csv_delimiter, json_handler=self._json_handler
                    )
                    all_documents.append(documents)

            _raise_on_no_documents(all_documents, document_type, directory_path)

            combined = _combine_documents(all_documents)

            return self.add_documents_in_batches(
                combined,
                batch_size=batch_size,
                primary_key=primary_key,
                compress=compress,
            )

        responses: list[TaskInfo] = []
        for path in directory.iterdir():
            if path.suffix == f".{document_type}":
                documents = _load_documents_from_file(
                    path, csv_delimiter, json_handler=self._json_handler
                )
                responses.extend(
                    self.add_documents_in_batches(
                        documents,
                        batch_size=batch_size,
                        primary_key=primary_key,
                        compress=compress,
                    )
                )

        _raise_on_no_documents(responses, document_type, directory_path)

        return responses

    def add_documents_from_file(
        self,
        file_path: Path | str,
        primary_key: str | None = None,
        *,
        compress: bool = False,
    ) -> TaskInfo:
        """Add documents to the index from a json file.

        Args:
            file_path: Path to the json file.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            InvalidDocumentError: If the docucment is not a valid format for Meilisearch.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import Client
            >>> file_path = Path("/path/to/file.json")
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.add_documents_from_file(file_path)
        """
        documents = _load_documents_from_file(file_path, json_handler=self._json_handler)

        return self.add_documents(documents, primary_key=primary_key, compress=compress)

    def add_documents_from_file_in_batches(
        self,
        file_path: Path | str,
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
        csv_delimiter: str | None = None,
        compress: bool = False,
    ) -> list[TaskInfo]:
        """Adds documents form a json file in batches to reduce RAM usage with indexing.

        Args:
            file_path: Path to the json file.
            batch_size: The number of documents that should be included in each batch.
                Defaults to 1000.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            List of update ids to track the action.

        Raises:
            InvalidDocumentError: If the docucment is not a valid format for Meilisearch.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import Client
            >>> file_path = Path("/path/to/file.json")
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.add_documents_from_file_in_batches(file_path)
        """
        documents = _load_documents_from_file(
            file_path, csv_delimiter, json_handler=self._json_handler
        )

        return self.add_documents_in_batches(
            documents,
            batch_size=batch_size,
            primary_key=primary_key,
            compress=compress,
        )

    def add_documents_from_raw_file(
        self,
        file_path: Path | str,
        primary_key: str | None = None,
        *,
        csv_delimiter: str | None = None,
        compress: bool = False,
    ) -> TaskInfo:
        """Directly send csv or ndjson files to Meilisearch without pre-processing.

        The can reduce RAM usage from Meilisearch during indexing, but does not include the option
        for batching.

        Args:
            file_path: The path to the file to send to Meilisearch. Only csv and ndjson files are
                allowed.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task.

        Raises:
            ValueError: If the file is not a csv or ndjson file, or if a csv_delimiter is sent for
                a non-csv file.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import Client
            >>> file_path = Path("/path/to/file.csv")
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.add_documents_from_raw_file(file_path)
        """
        upload_path = Path(file_path) if isinstance(file_path, str) else file_path
        if not upload_path.exists():
            raise MeilisearchError("No file found at the specified path")

        if upload_path.suffix not in (".csv", ".ndjson"):
            raise ValueError("Only csv and ndjson files can be sent as binary files")

        if csv_delimiter and upload_path.suffix != ".csv":
            raise ValueError("A csv_delimiter can only be used with csv files")

        if (
            csv_delimiter
            and len(csv_delimiter) != 1
            or csv_delimiter
            and not csv_delimiter.isascii()
        ):
            raise ValueError("csv_delimiter must be a single ascii character")

        content_type = "text/csv" if upload_path.suffix == ".csv" else "application/x-ndjson"
        parameters = {}

        if primary_key:
            parameters["primaryKey"] = primary_key
        if csv_delimiter:
            parameters["csvDelimiter"] = csv_delimiter

        if parameters:
            url = _build_encoded_url(self._documents_url, parameters)
        else:
            url = self._documents_url

        with open(upload_path) as f:
            data = f.read()

        response = self._http_requests.post(
            url, body=data, content_type=content_type, compress=compress
        )

        return TaskInfo(**response.json())

    def edit_documents(
        self, function: str, *, context: JsonDict | None = None, filter: str | None = None
    ) -> TaskInfo:
        """Edit documents with a function.

        Edit documents is only available in Meilisearch >= v1.10.0, and is experimental in
        Meilisearch v1.10.0. In order to use this feature you first need to enable it by
        sending a PATCH request to /experimental-features with { "editDocumentsByFunction": true }.

        Args:
            function: Rhai function to use to update the documents.
            context: Parameters to use in the function. Defaults to None.
            filter: Filter the documents before applying the function. Defaults to None.

        Returns:
            The details of the task.

        Raises:
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.edit_documents("doc.title = `${doc.title.to_upper()}`")
        """
        url = f"{self._documents_url}/edit"
        payload: JsonDict = {"function": function}

        if context:
            payload["context"] = context

        if filter:
            payload["filter"] = filter

        response = self._http_requests.post(url, payload)

        return TaskInfo(**response.json())

    def update_documents(
        self,
        documents: Sequence[JsonMapping],
        primary_key: str | None = None,
        *,
        compress: bool = False,
    ) -> TaskInfo:
        """Update documents in the index.

        Args:
            documents: List of documents.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> documents = [
            >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
            >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
            >>> ]
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_documents(documents)
        """
        if primary_key:
            url = _build_encoded_url(self._documents_url, {"primaryKey": primary_key})
        else:
            url = self._documents_url

        if self._pre_update_documents_plugins:
            pre = Index._run_plugins(
                self._pre_update_documents_plugins,
                Event.PRE,
                documents=documents,
                primary_key=primary_key,
            )
            if pre.get("document_result"):
                documents = pre["document_result"]

        response = self._http_requests.put(url, documents, compress=compress)
        result = TaskInfo(**response.json())
        if self._post_update_documents_plugins:
            post = Index._run_plugins(
                self._post_update_documents_plugins, Event.POST, result=result
            )
            if isinstance(post.get("generic_result"), TaskInfo):
                result = post["generic_result"]

        return result

    def update_documents_in_batches(
        self,
        documents: Sequence[JsonMapping],
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
        compress: bool = False,
    ) -> list[TaskInfo]:
        """Update documents in batches to reduce RAM usage with indexing.

        Each batch tries to fill the max_payload_size

        Args:
            documents: List of documents.
            batch_size: The number of documents that should be included in each batch.
                Defaults to 1000.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            List of update ids to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> documents = [
            >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
            >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
            >>> ]
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_documents_in_batches(documents)
        """
        return [
            self.update_documents(x, primary_key, compress=compress)
            for x in _batch(documents, batch_size)
        ]

    def update_documents_from_directory(
        self,
        directory_path: Path | str,
        *,
        primary_key: str | None = None,
        document_type: str = "json",
        csv_delimiter: str | None = None,
        combine_documents: bool = True,
        compress: bool = False,
    ) -> list[TaskInfo]:
        """Load all json files from a directory and update the documents.

        Args:
            directory_path: Path to the directory that contains the json files.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            document_type: The type of document being added. Accepted types are json, csv, and
                ndjson. For csv files the first row of the document should be a header row contining
                the field names, and ever for should have a title.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            combine_documents: If set to True this will combine the documents from all the files
                before indexing them. Defaults to True.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            InvalidDocumentError: If the docucment is not a valid format for Meilisearch.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import Client
            >>> directory_path = Path("/path/to/directory/containing/files")
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_documents_from_directory(directory_path)
        """
        directory = Path(directory_path) if isinstance(directory_path, str) else directory_path

        if combine_documents:
            all_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = _load_documents_from_file(
                        path, csv_delimiter, json_handler=self._json_handler
                    )
                    all_documents.append(documents)

            _raise_on_no_documents(all_documents, document_type, directory_path)

            combined = _combine_documents(all_documents)

            response = self.update_documents(combined, primary_key, compress=compress)
            return [response]

        responses = []
        for path in directory.iterdir():
            if path.suffix == f".{document_type}":
                documents = _load_documents_from_file(
                    path, csv_delimiter, json_handler=self._json_handler
                )
                responses.append(self.update_documents(documents, primary_key, compress=compress))

        _raise_on_no_documents(responses, document_type, directory_path)

        return responses

    def update_documents_from_directory_in_batches(
        self,
        directory_path: Path | str,
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
        document_type: str = "json",
        csv_delimiter: str | None = None,
        combine_documents: bool = True,
        compress: bool = False,
    ) -> list[TaskInfo]:
        """Load all json files from a directory and update the documents.

        Args:
            directory_path: Path to the directory that contains the json files.
            batch_size: The number of documents that should be included in each batch.
                Defaults to 1000.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            document_type: The type of document being added. Accepted types are json, csv, and
                ndjson. For csv files the first row of the document should be a header row contining
                the field names, and ever for should have a title.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            combine_documents: If set to True this will combine the documents from all the files
                before indexing them. Defaults to True.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            List of update ids to track the action.

        Raises:
            InvalidDocumentError: If the docucment is not a valid format for Meilisearch.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import Client
            >>> directory_path = Path("/path/to/directory/containing/files")
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_documents_from_directory_in_batches(directory_path)
        """
        directory = Path(directory_path) if isinstance(directory_path, str) else directory_path

        if combine_documents:
            all_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = _load_documents_from_file(
                        path, csv_delimiter, json_handler=self._json_handler
                    )
                    all_documents.append(documents)

            _raise_on_no_documents(all_documents, document_type, directory_path)

            combined = _combine_documents(all_documents)

            return self.update_documents_in_batches(
                combined,
                batch_size=batch_size,
                primary_key=primary_key,
                compress=compress,
            )

        responses: list[TaskInfo] = []

        for path in directory.iterdir():
            if path.suffix == f".{document_type}":
                documents = _load_documents_from_file(
                    path, csv_delimiter, json_handler=self._json_handler
                )
                responses.extend(
                    self.update_documents_in_batches(
                        documents,
                        batch_size=batch_size,
                        primary_key=primary_key,
                        compress=compress,
                    )
                )

        _raise_on_no_documents(responses, document_type, directory_path)

        return responses

    def update_documents_from_file(
        self,
        file_path: Path | str,
        primary_key: str | None = None,
        csv_delimiter: str | None = None,
        *,
        compress: bool = False,
    ) -> TaskInfo:
        """Add documents in the index from a json file.

        Args:
            file_path: Path to the json file.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import Client
            >>> file_path = Path("/path/to/file.json")
            >>> client = Client("http://localhost.com", "masterKey") as client:
            >>> index = client.index("movies")
            >>> index.update_documents_from_file(file_path)
        """
        documents = _load_documents_from_file(
            file_path, csv_delimiter, json_handler=self._json_handler
        )

        return self.update_documents(documents, primary_key=primary_key, compress=compress)

    def update_documents_from_file_in_batches(
        self,
        file_path: Path | str,
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
        compress: bool = False,
    ) -> list[TaskInfo]:
        """Updates documents form a json file in batches to reduce RAM usage with indexing.

        Args:
            file_path: Path to the json file.
            batch_size: The number of documents that should be included in each batch.
                Defaults to 1000.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            List of update ids to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import Client
            >>> file_path = Path("/path/to/file.json")
            >>> client = Client("http://localhost.com", "masterKey") as client:
            >>> index = client.index("movies")
            >>> index.update_documents_from_file_in_batches(file_path)
        """
        documents = _load_documents_from_file(file_path, json_handler=self._json_handler)

        return self.update_documents_in_batches(
            documents,
            batch_size=batch_size,
            primary_key=primary_key,
            compress=compress,
        )

    def update_documents_from_raw_file(
        self,
        file_path: Path | str,
        primary_key: str | None = None,
        csv_delimiter: str | None = None,
        *,
        compress: bool = False,
    ) -> TaskInfo:
        """Directly send csv or ndjson files to Meilisearch without pre-processing.

        The can reduce RAM usage from Meilisearch during indexing, but does not include the option
        for batching.

        Args:
            file_path: The path to the file to send to Meilisearch. Only csv and ndjson files are
                allowed.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            ValueError: If the file is not a csv or ndjson file, or if a csv_delimiter is sent for
                a non-csv file.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from pathlib import Path
            >>> from meilisearch_python_sdk import Client
            >>> file_path = Path("/path/to/file.csv")
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_documents_from_raw_file(file_path)
        """
        upload_path = Path(file_path) if isinstance(file_path, str) else file_path
        if not upload_path.exists():
            raise MeilisearchError("No file found at the specified path")

        if upload_path.suffix not in (".csv", ".ndjson"):
            raise ValueError("Only csv and ndjson files can be sent as binary files")

        if csv_delimiter and upload_path.suffix != ".csv":
            raise ValueError("A csv_delimiter can only be used with csv files")

        if (
            csv_delimiter
            and len(csv_delimiter) != 1
            or csv_delimiter
            and not csv_delimiter.isascii()
        ):
            raise ValueError("csv_delimiter must be a single ascii character")

        content_type = "text/csv" if upload_path.suffix == ".csv" else "application/x-ndjson"
        parameters = {}

        if primary_key:
            parameters["primaryKey"] = primary_key
        if csv_delimiter:
            parameters["csvDelimiter"] = csv_delimiter

        if parameters:
            url = _build_encoded_url(self._documents_url, parameters)
        else:
            url = self._documents_url

        with open(upload_path) as f:
            data = f.read()

        response = self._http_requests.put(
            url, body=data, content_type=content_type, compress=compress
        )

        return TaskInfo(**response.json())

    def delete_document(self, document_id: str) -> TaskInfo:
        """Delete one document from the index.

        Args:
            document_id: Unique identifier of the document.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.delete_document("1234")
        """
        if self._pre_delete_document_plugins:
            Index._run_plugins(
                self._pre_delete_document_plugins, Event.PRE, document_id=document_id
            )

        response = self._http_requests.delete(f"{self._documents_url}/{document_id}")
        result = TaskInfo(**response.json())
        if self._post_delete_document_plugins:
            post = Index._run_plugins(self._post_delete_document_plugins, Event.POST, result=result)
            if isinstance(post.get("generic_result"), TaskInfo):
                result = post["generic_result"]

        return result

    def delete_documents(self, ids: list[str]) -> TaskInfo:
        """Delete multiple documents from the index.

        Args:
            ids: List of unique identifiers of documents.

        Returns:
            List of update ids to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.delete_documents(["1234", "5678"])
        """
        if self._pre_delete_documents_plugins:
            Index._run_plugins(self._pre_delete_documents_plugins, Event.PRE, ids=ids)

        response = self._http_requests.post(f"{self._documents_url}/delete-batch", ids)
        result = TaskInfo(**response.json())
        if self._post_delete_documents_plugins:
            post = Index._run_plugins(
                self._post_delete_documents_plugins, Event.POST, result=result
            )
            if isinstance(post.get("generic_result"), TaskInfo):
                result = post["generic_result"]

        return result

    def delete_documents_by_filter(self, filter: Filter) -> TaskInfo:
        """Delete documents from the index by filter.

        Args:
            filter: The filter value information.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.delete_documents_by_filter("genre=horor"))
        """
        if self._pre_delete_documents_by_filter_plugins:
            Index._run_plugins(
                self._pre_delete_documents_by_filter_plugins, Event.PRE, filter=filter
            )

        response = self._http_requests.post(
            f"{self._documents_url}/delete", body={"filter": filter}
        )
        result = TaskInfo(**response.json())
        if self._post_delete_documents_by_filter_plugins:
            post = Index._run_plugins(
                self._post_delete_documents_by_filter_plugins, Event.POST, result=result
            )
            if isinstance(post.get("generic_result"), TaskInfo):
                result = post["generic_result"]

        return result

    def delete_documents_in_batches_by_filter(
        self, filters: list[str | list[str | list[str]]]
    ) -> list[TaskInfo]:
        """Delete batches of documents from the index by filter.

        Args:
            filters: A list of filter value information.

        Returns:
            The a list of details of the task statuses.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.delete_documents_in_batches_by_filter(
            >>>     [
            >>>         "genre=horor"),
            >>>         "release_date=1520035200"),
            >>>     ]
            >>> )
        """
        return [self.delete_documents_by_filter(filter) for filter in filters]

    def delete_all_documents(self) -> TaskInfo:
        """Delete all documents from the index.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.delete_all_document()
        """
        if self._pre_delete_all_documents_plugins:
            Index._run_plugins(self._pre_delete_all_documents_plugins, Event.PRE)

        response = self._http_requests.delete(self._documents_url)
        result = TaskInfo(**response.json())
        if self._post_delete_all_documents_plugins:
            post = Index._run_plugins(
                self._post_delete_all_documents_plugins, Event.POST, result=result
            )
            if isinstance(post.get("generic_result"), TaskInfo):
                result = post["generic_result"]

        return result

    def get_settings(self) -> MeilisearchSettings:
        """Get settings of the index.

        Returns:
            Settings of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> settings = index.get_settings()
        """
        response = self._http_requests.get(self._settings_url)
        response_json = response.json()
        settings = MeilisearchSettings(**response_json)

        if response_json.get("embedders"):
            # TODO: Add back after embedder setting issue fixed https://github.com/meilisearch/meilisearch/issues/4585
            settings.embedders = _embedder_json_to_settings_model(  # pragma: no cover
                response_json["embedders"]
            )

        return settings

    def update_settings(self, body: MeilisearchSettings, *, compress: bool = False) -> TaskInfo:
        """Update settings of the index.

        Args:
            body: Settings of the index.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> from meilisearch_python_sdk import MeilisearchSettings
            >>> new_settings = MeilisearchSettings(
            >>>     synonyms={"wolverine": ["xmen", "logan"], "logan": ["wolverine"]},
            >>>     stop_words=["the", "a", "an"],
            >>>     ranking_rules=[
            >>>         "words",
            >>>         "typo",
            >>>         "proximity",
            >>>         "attribute",
            >>>         "sort",
            >>>         "exactness",
            >>>         "release_date:desc",
            >>>         "rank:desc",
            >>>    ],
            >>>    filterable_attributes=["genre", "director"],
            >>>    distinct_attribute="url",
            >>>    searchable_attributes=["title", "description", "genre"],
            >>>    displayed_attributes=["title", "description", "genre", "release_date"],
            >>>    sortable_attributes=["title", "release_date"],
            >>> )
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_settings(new_settings)
        """
        body_dict = {
            k: v
            for k, v in body.model_dump(by_alias=True, exclude_none=True).items()
            if v is not None
        }
        response = self._http_requests.patch(self._settings_url, body_dict, compress=compress)

        return TaskInfo(**response.json())

    def reset_settings(self) -> TaskInfo:
        """Reset settings of the index to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_settings()
        """
        response = self._http_requests.delete(self._settings_url)

        return TaskInfo(**response.json())

    def get_ranking_rules(self) -> list[str]:
        """Get ranking rules of the index.

        Returns:
            List containing the ranking rules of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> ranking_rules = index.get_ranking_rules()
        """
        response = self._http_requests.get(f"{self._settings_url}/ranking-rules")

        return response.json()

    def update_ranking_rules(self, ranking_rules: list[str], *, compress: bool = False) -> TaskInfo:
        """Update ranking rules of the index.

        Args:
            ranking_rules: List containing the ranking rules.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> ranking_rules=[
            >>>      "words",
            >>>      "typo",
            >>>      "proximity",
            >>>      "attribute",
            >>>      "sort",
            >>>      "exactness",
            >>>      "release_date:desc",
            >>>      "rank:desc",
            >>> ],
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_ranking_rules(ranking_rules)
        """
        response = self._http_requests.put(
            f"{self._settings_url}/ranking-rules", ranking_rules, compress=compress
        )

        return TaskInfo(**response.json())

    def reset_ranking_rules(self) -> TaskInfo:
        """Reset ranking rules of the index to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_ranking_rules()
        """
        response = self._http_requests.delete(f"{self._settings_url}/ranking-rules")

        return TaskInfo(**response.json())

    def get_distinct_attribute(self) -> str | None:
        """Get distinct attribute of the index.

        Returns:
            String containing the distinct attribute of the index. If no distinct attribute
                `None` is returned.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> distinct_attribute = index.get_distinct_attribute()
        """
        response = self._http_requests.get(f"{self._settings_url}/distinct-attribute")

        if not response.json():
            return None

        return response.json()

    def update_distinct_attribute(self, body: str, *, compress: bool = False) -> TaskInfo:
        """Update distinct attribute of the index.

        Args:
            body: Distinct attribute.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_distinct_attribute("url")
        """
        response = self._http_requests.put(
            f"{self._settings_url}/distinct-attribute", body, compress=compress
        )

        return TaskInfo(**response.json())

    def reset_distinct_attribute(self) -> TaskInfo:
        """Reset distinct attribute of the index to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_distinct_attributes()
        """
        response = self._http_requests.delete(f"{self._settings_url}/distinct-attribute")

        return TaskInfo(**response.json())

    def get_searchable_attributes(self) -> list[str]:
        """Get searchable attributes of the index.

        Returns:
            List containing the searchable attributes of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> searchable_attributes = index.get_searchable_attributes()
        """
        response = self._http_requests.get(f"{self._settings_url}/searchable-attributes")

        return response.json()

    def update_searchable_attributes(self, body: list[str], *, compress: bool = False) -> TaskInfo:
        """Update searchable attributes of the index.

        Args:
            body: List containing the searchable attributes.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_searchable_attributes(["title", "description", "genre"])
        """
        response = self._http_requests.put(
            f"{self._settings_url}/searchable-attributes", body, compress=compress
        )

        return TaskInfo(**response.json())

    def reset_searchable_attributes(self) -> TaskInfo:
        """Reset searchable attributes of the index to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_searchable_attributes()
        """
        response = self._http_requests.delete(f"{self._settings_url}/searchable-attributes")

        return TaskInfo(**response.json())

    def get_displayed_attributes(self) -> list[str]:
        """Get displayed attributes of the index.

        Returns:
            List containing the displayed attributes of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> displayed_attributes = index.get_displayed_attributes()
        """
        response = self._http_requests.get(f"{self._settings_url}/displayed-attributes")

        return response.json()

    def update_displayed_attributes(self, body: list[str], *, compress: bool = False) -> TaskInfo:
        """Update displayed attributes of the index.

        Args:
            body: List containing the displayed attributes.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_displayed_attributes(
            >>>     ["title", "description", "genre", "release_date"]
            >>> )
        """
        response = self._http_requests.put(
            f"{self._settings_url}/displayed-attributes", body, compress=compress
        )

        return TaskInfo(**response.json())

    def reset_displayed_attributes(self) -> TaskInfo:
        """Reset displayed attributes of the index to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_displayed_attributes()
        """
        response = self._http_requests.delete(f"{self._settings_url}/displayed-attributes")

        return TaskInfo(**response.json())

    def get_stop_words(self) -> list[str] | None:
        """Get stop words of the index.

        Returns:
            List containing the stop words of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> stop_words = index.get_stop_words()
        """
        response = self._http_requests.get(f"{self._settings_url}/stop-words")

        if not response.json():
            return None

        return response.json()

    def update_stop_words(self, body: list[str], *, compress: bool = False) -> TaskInfo:
        """Update stop words of the index.

        Args:
            body: List containing the stop words of the index.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_stop_words(["the", "a", "an"])
        """
        response = self._http_requests.put(
            f"{self._settings_url}/stop-words", body, compress=compress
        )

        return TaskInfo(**response.json())

    def reset_stop_words(self) -> TaskInfo:
        """Reset stop words of the index to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_stop_words()
        """
        response = self._http_requests.delete(f"{self._settings_url}/stop-words")

        return TaskInfo(**response.json())

    def get_synonyms(self) -> dict[str, list[str]] | None:
        """Get synonyms of the index.

        Returns:
            The synonyms of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> synonyms = index.get_synonyms()
        """
        response = self._http_requests.get(f"{self._settings_url}/synonyms")

        if not response.json():
            return None

        return response.json()

    def update_synonyms(self, body: dict[str, list[str]], *, compress: bool = False) -> TaskInfo:
        """Update synonyms of the index.

        Args:
            body: The synonyms of the index.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey") as client:
            >>> index = client.index("movies")
            >>> index.update_synonyms(
            >>>     {"wolverine": ["xmen", "logan"], "logan": ["wolverine"]}
            >>> )
        """
        response = self._http_requests.put(
            f"{self._settings_url}/synonyms", body, compress=compress
        )

        return TaskInfo(**response.json())

    def reset_synonyms(self) -> TaskInfo:
        """Reset synonyms of the index to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_synonyms()
        """
        response = self._http_requests.delete(f"{self._settings_url}/synonyms")

        return TaskInfo(**response.json())

    def get_filterable_attributes(self) -> list[str] | list[FilterableAttributes] | None:
        """Get filterable attributes of the index.

        Returns:
            List containing the filterable attributes of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> filterable_attributes = index.get_filterable_attributes()
        """
        response = self._http_requests.get(f"{self._settings_url}/filterable-attributes")

        if not response.json():
            return None

        response_json = response.json()

        if isinstance(response_json[0], str):
            return response_json

        filterable_attributes = []
        for r in response_json:
            filterable_attributes.append(
                FilterableAttributes(
                    attribute_patterns=r["attributePatterns"],
                    features=FilterableAttributeFeatures(**r["features"]),
                )
            )

        return filterable_attributes

    def update_filterable_attributes(
        self, body: list[str] | list[FilterableAttributes], *, compress: bool = False
    ) -> TaskInfo:
        """Update filterable attributes of the index.

        Args:
            body: List containing the filterable attributes of the index.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_filterable_attributes(["genre", "director"])
        """
        payload: list[str | JsonDict] = []

        for b in body:
            if isinstance(b, FilterableAttributes):
                payload.append(b.model_dump(by_alias=True))
            else:
                payload.append(b)

        response = self._http_requests.put(
            f"{self._settings_url}/filterable-attributes", payload, compress=compress
        )

        return TaskInfo(**response.json())

    def reset_filterable_attributes(self) -> TaskInfo:
        """Reset filterable attributes of the index to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_filterable_attributes()
        """
        response = self._http_requests.delete(f"{self._settings_url}/filterable-attributes")

        return TaskInfo(**response.json())

    def get_sortable_attributes(self) -> list[str]:
        """Get sortable attributes of the AsyncIndex.

        Returns:
            List containing the sortable attributes of the AsyncIndex.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> sortable_attributes = index.get_sortable_attributes()
        """
        response = self._http_requests.get(f"{self._settings_url}/sortable-attributes")

        return response.json()

    def update_sortable_attributes(
        self, sortable_attributes: list[str], *, compress: bool = False
    ) -> TaskInfo:
        """Get sortable attributes of the AsyncIndex.

        Args:
            sortable_attributes: List of attributes for searching.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_sortable_attributes(["title", "release_date"])
        """
        response = self._http_requests.put(
            f"{self._settings_url}/sortable-attributes", sortable_attributes, compress=compress
        )

        return TaskInfo(**response.json())

    def reset_sortable_attributes(self) -> TaskInfo:
        """Reset sortable attributes of the index to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_sortable_attributes()
        """
        response = self._http_requests.delete(f"{self._settings_url}/sortable-attributes")

        return TaskInfo(**response.json())

    def get_typo_tolerance(self) -> TypoTolerance:
        """Get typo tolerance for the index.

        Returns:
            TypoTolerance for the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> sortable_attributes = index.get_typo_tolerance()
        """
        response = self._http_requests.get(f"{self._settings_url}/typo-tolerance")

        return TypoTolerance(**response.json())

    def update_typo_tolerance(
        self, typo_tolerance: TypoTolerance, *, compress: bool = False
    ) -> TaskInfo:
        """Update typo tolerance.

        Args:
            typo_tolerance: Typo tolerance settings.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> TypoTolerance(enabled=False)
            >>> index.update_typo_tolerance()
        """
        response = self._http_requests.patch(
            f"{self._settings_url}/typo-tolerance",
            typo_tolerance.model_dump(by_alias=True, exclude_unset=True),
            compress=compress,
        )

        return TaskInfo(**response.json())

    def reset_typo_tolerance(self) -> TaskInfo:
        """Reset typo tolerance to default values.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_typo_tolerance()
        """
        response = self._http_requests.delete(f"{self._settings_url}/typo-tolerance")

        return TaskInfo(**response.json())

    def get_faceting(self) -> Faceting:
        """Get faceting for the index.

        Returns:
            Faceting for the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> faceting = index.get_faceting()
        """
        response = self._http_requests.get(f"{self._settings_url}/faceting")

        return Faceting(**response.json())

    def update_faceting(self, faceting: Faceting, *, compress: bool = False) -> TaskInfo:
        """Partially update the faceting settings for an index.

        Args:
            faceting: Faceting values.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_faceting(faceting=Faceting(max_values_per_facet=100))
        """
        response = self._http_requests.patch(
            f"{self._settings_url}/faceting",
            faceting.model_dump(by_alias=True),
            compress=compress,
        )

        return TaskInfo(**response.json())

    def reset_faceting(self) -> TaskInfo:
        """Reset an index's faceting settings to their default value.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_faceting()
        """
        response = self._http_requests.delete(f"{self._settings_url}/faceting")

        return TaskInfo(**response.json())

    def get_pagination(self) -> Pagination:
        """Get pagination settings for the index.

        Returns:
            Pagination for the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> pagination_settings = index.get_pagination()
        """
        response = self._http_requests.get(f"{self._settings_url}/pagination")

        return Pagination(**response.json())

    def update_pagination(self, settings: Pagination, *, compress: bool = False) -> TaskInfo:
        """Partially update the pagination settings for an index.

        Args:
            settings: settings for pagination.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> from meilisearch_python_sdk.models.settings import Pagination
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_pagination(settings=Pagination(max_total_hits=123))
        """
        response = self._http_requests.patch(
            f"{self._settings_url}/pagination",
            settings.model_dump(by_alias=True),
            compress=compress,
        )

        return TaskInfo(**response.json())

    def reset_pagination(self) -> TaskInfo:
        """Reset an index's pagination settings to their default value.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_pagination()
        """
        response = self._http_requests.delete(f"{self._settings_url}/pagination")

        return TaskInfo(**response.json())

    def get_separator_tokens(self) -> list[str]:
        """Get separator token settings for the index.

        Returns:
            Separator tokens for the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> separator_token_settings = index.get_separator_tokens()
        """
        response = self._http_requests.get(f"{self._settings_url}/separator-tokens")

        return response.json()

    def update_separator_tokens(
        self, separator_tokens: list[str], *, compress: bool = False
    ) -> TaskInfo:
        """Update the separator tokens settings for an index.

        Args:
            separator_tokens: List of separator tokens.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_separator_tokens(separator_tokenes=["|", "/")
        """
        response = self._http_requests.put(
            f"{self._settings_url}/separator-tokens", separator_tokens, compress=compress
        )

        return TaskInfo(**response.json())

    def reset_separator_tokens(self) -> TaskInfo:
        """Reset an index's separator tokens settings to the default value.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_separator_tokens()
        """
        response = self._http_requests.delete(f"{self._settings_url}/separator-tokens")

        return TaskInfo(**response.json())

    def get_non_separator_tokens(self) -> list[str]:
        """Get non-separator token settings for the index.

        Returns:
            Non-separator tokens for the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> non_separator_token_settings = index.get_non_separator_tokens()
        """
        response = self._http_requests.get(f"{self._settings_url}/non-separator-tokens")

        return response.json()

    def update_non_separator_tokens(
        self, non_separator_tokens: list[str], *, compress: bool = False
    ) -> TaskInfo:
        """Update the non-separator tokens settings for an index.

        Args:
            non_separator_tokens: List of non-separator tokens.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_non_separator_tokens(non_separator_tokens=["@", "#")
        """
        response = self._http_requests.put(
            f"{self._settings_url}/non-separator-tokens", non_separator_tokens, compress=compress
        )

        return TaskInfo(**response.json())

    def reset_non_separator_tokens(self) -> TaskInfo:
        """Reset an index's non-separator tokens settings to the default value.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_non_separator_tokens()
        """
        response = self._http_requests.delete(f"{self._settings_url}/non-separator-tokens")

        return TaskInfo(**response.json())

    def get_search_cutoff_ms(self) -> int | None:
        """Get search cutoff time in ms.

        Returns:
            Integer representing the search cutoff time in ms, or None.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> search_cutoff_ms_settings = index.get_search_cutoff_ms()
        """
        response = self._http_requests.get(f"{self._settings_url}/search-cutoff-ms")

        return response.json()

    def update_search_cutoff_ms(self, search_cutoff_ms: int, *, compress: bool = False) -> TaskInfo:
        """Update the search cutoff for an index.

        Args:
            search_cutoff_ms: Integer value of the search cutoff time in ms.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_search_cutoff_ms(100)
        """
        response = self._http_requests.put(
            f"{self._settings_url}/search-cutoff-ms", search_cutoff_ms, compress=compress
        )

        return TaskInfo(**response.json())

    def reset_search_cutoff_ms(self) -> TaskInfo:
        """Reset the search cutoff time to the default value.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_search_cutoff_ms()
        """
        response = self._http_requests.delete(f"{self._settings_url}/search-cutoff-ms")

        return TaskInfo(**response.json())

    def get_word_dictionary(self) -> list[str]:
        """Get word dictionary settings for the index.

        Returns:
            Word dictionary for the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> word_dictionary = index.get_word_dictionary()
        """
        response = self._http_requests.get(f"{self._settings_url}/dictionary")

        return response.json()

    def update_word_dictionary(self, dictionary: list[str], *, compress: bool = False) -> TaskInfo:
        """Update the word dictionary settings for an index.

        Args:
            dictionary: List of dictionary values.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_word_dictionary(dictionary=["S.O.S", "S.O")
        """
        response = self._http_requests.put(
            f"{self._settings_url}/dictionary", dictionary, compress=compress
        )

        return TaskInfo(**response.json())

    def reset_word_dictionary(self) -> TaskInfo:
        """Reset an index's word dictionary settings to the default value.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_word_dictionary()
        """
        response = self._http_requests.delete(f"{self._settings_url}/dictionary")

        return TaskInfo(**response.json())

    def get_proximity_precision(self) -> ProximityPrecision:
        """Get proximity precision settings for the index.

        Returns:
            Proximity precision for the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> proximity_precision = index.get_proximity_precision()
        """
        response = self._http_requests.get(f"{self._settings_url}/proximity-precision")

        return ProximityPrecision[to_snake(response.json()).upper()]

    def update_proximity_precision(
        self, proximity_precision: ProximityPrecision, *, compress: bool = False
    ) -> TaskInfo:
        """Update the proximity precision settings for an index.

        Args:
            proximity_precision: The proximity precision value.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> from meilisearch_python_sdk.models.settings import ProximityPrecision
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_proximity_precision(ProximityPrecision.BY_ATTRIBUTE)
        """
        response = self._http_requests.put(
            f"{self._settings_url}/proximity-precision",
            proximity_precision.value,
            compress=compress,
        )

        return TaskInfo(**response.json())

    def reset_proximity_precision(self) -> TaskInfo:
        """Reset an index's proximity precision settings to the default value.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_proximity_precision()
        """
        response = self._http_requests.delete(f"{self._settings_url}/proximity-precision")

        return TaskInfo(**response.json())

    def get_embedders(self) -> Embedders | None:
        """Get embedder settings for the index.

        Returns:
            Embedders for the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> embedders = await index.get_embedders()
        """
        response = self._http_requests.get(f"{self._settings_url}/embedders")

        return _embedder_json_to_embedders_model(response.json())

    def update_embedders(self, embedders: Embedders, *, compress: bool = False) -> TaskInfo:
        """Update the embedders settings for an index.

        Args:
            embedders: The embedders value.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> from meilisearch_python_sdk.models.settings import Embedders, UserProvidedEmbedder
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_embedders(
            >>>     Embedders(embedders={dimensions=512)})
            >>> )
        """
        payload = {}
        for key, embedder in embedders.embedders.items():
            payload[key] = {
                k: v
                for k, v in embedder.model_dump(by_alias=True, exclude_none=True).items()
                if v is not None
            }

        response = self._http_requests.patch(
            f"{self._settings_url}/embedders", payload, compress=compress
        )

        return TaskInfo(**response.json())

    # TODO: Add back after embedder setting issue fixed https://github.com/meilisearch/meilisearch/issues/4585
    def reset_embedders(self) -> TaskInfo:  # pragma: no cover
        """Reset an index's embedders settings to the default value.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import Client
            >>> client = AsyncClient("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_embedders()
        """
        response = self._http_requests.delete(f"{self._settings_url}/embedders")

        return TaskInfo(**response.json())

    def get_localized_attributes(self) -> list[LocalizedAttributes] | None:
        """Get localized attributes settings for the index.

        Returns:
            Localized attributes for the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> localized_attributes = await index.get_localized_attributes()
        """
        response = self._http_requests.get(f"{self._settings_url}/localized-attributes")

        if not response.json():
            return None

        return [LocalizedAttributes(**x) for x in response.json()]

    def update_localized_attributes(
        self, localized_attributes: list[LocalizedAttributes], *, compress: bool = False
    ) -> TaskInfo:
        """Update the localized attributes settings for an index.

        Args:
            localized_attributes: The localized attributes value.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            Task to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import AsyncClient
            >>> from meilisearch_python_sdk.models.settings import LocalizedAttributes
            >>>
            >>>
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_localized_attributes([
            >>>     LocalizedAttributes(locales=["eng", "spa"], attribute_patterns=["*"]),
            >>>     LocalizedAttributes(locales=["ita"], attribute_patterns=["*_it"]),
            >>> ])
        """
        payload = [x.model_dump(by_alias=True) for x in localized_attributes]
        response = self._http_requests.put(
            f"{self._settings_url}/localized-attributes", payload, compress=compress
        )

        return TaskInfo(**response.json())

    def reset_localized_attributes(self) -> TaskInfo:
        """Reset an index's localized attributes settings to the default value.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import AsyncClient
            >>> Client("http://localhost.com", "masterKey") as client:
            >>> index = client.index("movies")
            >>> index.reset_localized_attributes()
        """
        response = self._http_requests.delete(f"{self._settings_url}/localized-attributes")

        return TaskInfo(**response.json())

    def get_facet_search(self) -> bool:
        """Get setting for facet search opt-out.

        Returns:
            True if facet search is enabled or False if not.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> facet_search = await index.get_facet_search()
        """
        response = self._http_requests.get(f"{self._settings_url}/facet-search")

        return response.json()

    def update_facet_search(self, facet_search: bool, *, compress: bool = False) -> TaskInfo:
        """Update setting for facet search opt-out.

        Args:
            facet_search: Boolean indicating if facet search should be disabled.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_facet_search(True)
        """
        response = self._http_requests.put(
            f"{self._settings_url}/facet-search",
            facet_search,
            compress=compress,
        )

        return TaskInfo(**response.json())

    def reset_facet_search(self) -> TaskInfo:
        """Reset the facet search opt-out settings.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> await index.reset_facet_search()
        """
        response = self._http_requests.delete(f"{self._settings_url}/facet-search")

        return TaskInfo(**response.json())

    def get_prefix_search(self) -> bool:
        """Get setting for prefix search opt-out.

        Returns:
            True if prefix search is enabled or False if not.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> prefix_search = index.get_prefix_search()
        """
        response = self._http_requests.get(f"{self._settings_url}/prefix-search")

        return response.json()

    def update_prefix_search(
        self,
        prefix_search: Literal["disabled", "indexingTime", "searchTime"],
        *,
        compress: bool = False,
    ) -> TaskInfo:
        """Update setting for prefix search opt-out.

        Args:
            prefix_search: Value indicating prefix search setting.
            compress: If set to True the data will be sent in gzip format. Defaults to False.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_python_sdk import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.update_prefix_search("disabled")
        """
        response = self._http_requests.put(
            f"{self._settings_url}/prefix-search",
            prefix_search,
            compress=compress,
        )

        return TaskInfo(**response.json())

    def reset_prefix_search(self) -> TaskInfo:
        """Reset the prefix search opt-out settings.

        Returns:
            The details of the task status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples
            >>> from meilisearch_async_client import Client
            >>> client = Client("http://localhost.com", "masterKey")
            >>> index = client.index("movies")
            >>> index.reset_prefix_search()
        """
        response = self._http_requests.delete(f"{self._settings_url}/prefix-search")

        return TaskInfo(**response.json())

    @staticmethod
    def _run_plugins(
        plugins: Sequence[Plugin | DocumentPlugin | PostSearchPlugin],
        event: Event,
        **kwargs: Any,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {
            "generic_result": None,
            "document_result": None,
            "search_result": None,
        }
        generic_tasks = []
        document_tasks = []
        search_tasks = []
        for plugin in plugins:
            if _plugin_has_method(plugin, "run_plugin"):
                generic_tasks.append(plugin.run_plugin(event=event, **kwargs))  # type: ignore[union-attr]
            if _plugin_has_method(plugin, "run_document_plugin"):
                document_tasks.append(
                    plugin.run_document_plugin(event=event, **kwargs)  # type: ignore[union-attr]
                )
            if _plugin_has_method(plugin, "run_post_search_plugin"):
                search_tasks.append(
                    plugin.run_post_search_plugin(event=event, **kwargs)  # type: ignore[union-attr]
                )

        if generic_tasks:
            for result in reversed(generic_tasks):
                if result:
                    results["generic_result"] = result
                    break

        if document_tasks:
            results["document_result"] = document_tasks[-1]

        if search_tasks:
            results["search_result"] = search_tasks[-1]

        return results


async def _async_load_documents_from_file(
    file_path: Path | str,
    csv_delimiter: str | None = None,
    *,
    json_handler: BuiltinHandler | OrjsonHandler | UjsonHandler,
) -> list[dict[Any, Any]]:
    if isinstance(file_path, str):
        file_path = Path(file_path)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, partial(_validate_file_type, file_path))

    if file_path.suffix == ".csv":
        if (
            csv_delimiter
            and len(csv_delimiter) != 1
            or csv_delimiter
            and not csv_delimiter.isascii()
        ):
            raise ValueError("csv_delimiter must be a single ascii character")
        with open(file_path) as f:  # noqa: ASYNC230
            if csv_delimiter:
                documents = await loop.run_in_executor(
                    None, partial(DictReader, f, delimiter=csv_delimiter)
                )
            else:
                documents = await loop.run_in_executor(None, partial(DictReader, f))
            return list(documents)

    if file_path.suffix == ".ndjson":
        with open(file_path) as f:  # noqa: ASYNC230
            return [await loop.run_in_executor(None, partial(json_handler.loads, x)) for x in f]

    async with aiofiles.open(file_path) as f:  # type: ignore
        data = await f.read()  # type: ignore
        documents = await loop.run_in_executor(None, partial(json_handler.loads, data))

        if not isinstance(documents, list):
            raise InvalidDocumentError("Meilisearch requires documents to be in a list")

        return documents


def _batch(
    documents: Sequence[MutableMapping], batch_size: int
) -> Generator[Sequence[MutableMapping], None, None]:
    total_len = len(documents)
    for i in range(0, total_len, batch_size):
        yield documents[i : i + batch_size]


def _combine_documents(documents: list[list[Any]]) -> list[Any]:
    return [x for y in documents for x in y]


def _plugin_has_method(
    plugin: AsyncPlugin
    | AsyncDocumentPlugin
    | AsyncPostSearchPlugin
    | Plugin
    | DocumentPlugin
    | PostSearchPlugin,
    method: str,
) -> bool:
    check = getattr(plugin, method, None)
    if callable(check):
        return True

    return False


def _load_documents_from_file(
    file_path: Path | str,
    csv_delimiter: str | None = None,
    *,
    json_handler: BuiltinHandler | OrjsonHandler | UjsonHandler,
) -> list[dict[Any, Any]]:
    if isinstance(file_path, str):
        file_path = Path(file_path)

    _validate_file_type(file_path)

    if file_path.suffix == ".csv":
        if (
            csv_delimiter
            and len(csv_delimiter) != 1
            or csv_delimiter
            and not csv_delimiter.isascii()
        ):
            raise ValueError("csv_delimiter must be a single ascii character")
        with open(file_path) as f:
            if csv_delimiter:
                documents = DictReader(f, delimiter=csv_delimiter)
            else:
                documents = DictReader(f)
            return list(documents)

    if file_path.suffix == ".ndjson":
        with open(file_path) as f:
            return [json_handler.loads(x) for x in f]

    with open(file_path) as f:
        data = f.read()
        documents = json_handler.loads(data)

        if not isinstance(documents, list):
            raise InvalidDocumentError("Meilisearch requires documents to be in a list")

        return documents


def _raise_on_no_documents(
    documents: list[Any], document_type: str, directory_path: str | Path
) -> None:
    if not documents:
        raise MeilisearchError(f"No {document_type} files found in {directory_path}")


def _process_search_parameters(
    *,
    q: str | None = None,
    facet_name: str | None = None,
    facet_query: str | None = None,
    offset: int = 0,
    limit: int = 20,
    filter: Filter | None = None,
    facets: list[str] | None = None,
    attributes_to_retrieve: list[str] | None = None,
    attributes_to_crop: list[str] | None = None,
    crop_length: int = 200,
    attributes_to_highlight: list[str] | None = None,
    sort: list[str] | None = None,
    show_matches_position: bool = False,
    highlight_pre_tag: str = "<em>",
    highlight_post_tag: str = "</em>",
    crop_marker: str = "...",
    matching_strategy: Literal["all", "last", "frequency"] = "last",
    hits_per_page: int | None = None,
    page: int | None = None,
    attributes_to_search_on: list[str] | None = None,
    distinct: str | None = None,
    show_ranking_score: bool = False,
    show_ranking_score_details: bool = False,
    ranking_score_threshold: float | None = None,
    vector: list[float] | None = None,
    hybrid: Hybrid | None = None,
    locales: list[str] | None = None,
    retrieve_vectors: bool | None = None,
    exhaustive_facet_count: bool | None = None,
) -> JsonDict:
    if attributes_to_retrieve is None:
        attributes_to_retrieve = ["*"]

    body: JsonDict = {
        "q": q,
        "offset": offset,
        "limit": limit,
        "filter": filter,
        "facets": facets,
        "attributesToRetrieve": attributes_to_retrieve,
        "attributesToCrop": attributes_to_crop,
        "cropLength": crop_length,
        "attributesToHighlight": attributes_to_highlight,
        "sort": sort,
        "showMatchesPosition": show_matches_position,
        "highlightPreTag": highlight_pre_tag,
        "highlightPostTag": highlight_post_tag,
        "cropMarker": crop_marker,
        "matchingStrategy": matching_strategy,
        "hitsPerPage": hits_per_page,
        "page": page,
        "attributesToSearchOn": attributes_to_search_on,
        "showRankingScore": show_ranking_score,
        "rankingScoreThreshold": ranking_score_threshold,
    }

    if facet_name:
        body["facetName"] = facet_name

    if facet_query:
        body["facetQuery"] = facet_query

    if distinct:
        body["distinct"] = distinct

    if show_ranking_score_details:
        body["showRankingScoreDetails"] = show_ranking_score_details

    if vector:
        body["vector"] = vector

    if hybrid:
        body["hybrid"] = hybrid.model_dump(by_alias=True)

    if locales:
        body["locales"] = locales

    if retrieve_vectors is not None:
        body["retrieveVectors"] = retrieve_vectors

    if exhaustive_facet_count is not None:
        body["exhaustivefacetCount"] = exhaustive_facet_count

    return body


def _build_encoded_url(base_url: str, params: JsonMapping) -> str:
    return f"{base_url}?{urlencode(params)}"


# TODO: Add back after embedder setting issue fixed https://github.com/meilisearch/meilisearch/issues/4585
def _embedder_json_to_embedders_model(  # pragma: no cover
    embedder_json: JsonDict | None,
) -> Embedders | None:
    if not embedder_json:  # pragma: no cover
        return None

    embedders: dict[
        str,
        OpenAiEmbedder
        | HuggingFaceEmbedder
        | OllamaEmbedder
        | RestEmbedder
        | UserProvidedEmbedder
        | CompositeEmbedder,
    ] = {}
    for k, v in embedder_json.items():
        if v.get("source") == "openAi":
            embedders[k] = OpenAiEmbedder(**v)
        elif v.get("source") == "huggingFace":
            embedders[k] = HuggingFaceEmbedder(**v)
        elif v.get("source") == "ollama":
            embedders[k] = OllamaEmbedder(**v)
        elif v.get("source") == "rest":
            embedders[k] = RestEmbedder(**v)
        elif v.get("source") == "composit":
            embedders[k] = CompositeEmbedder(**v)
        else:
            embedders[k] = UserProvidedEmbedder(**v)

    return Embedders(embedders=embedders)


# TODO: Add back after embedder setting issue fixed https://github.com/meilisearch/meilisearch/issues/4585
def _embedder_json_to_settings_model(  # pragma: no cover
    embedder_json: JsonDict | None,
) -> (
    dict[
        str,
        OpenAiEmbedder
        | HuggingFaceEmbedder
        | OllamaEmbedder
        | RestEmbedder
        | UserProvidedEmbedder
        | CompositeEmbedder,
    ]
    | None
):
    if not embedder_json:  # pragma: no cover
        return None

    embedders: dict[
        str,
        OpenAiEmbedder
        | HuggingFaceEmbedder
        | OllamaEmbedder
        | RestEmbedder
        | UserProvidedEmbedder
        | CompositeEmbedder,
    ] = {}
    for k, v in embedder_json.items():
        if v.get("source") == "openAi":
            embedders[k] = OpenAiEmbedder(**v)
        elif v.get("source") == "huggingFace":
            embedders[k] = HuggingFaceEmbedder(**v)
        elif v.get("source") == "ollama":
            embedders[k] = OllamaEmbedder(**v)
        elif v.get("source") == "rest":
            embedders[k] = RestEmbedder(**v)
        elif v.get("source") == "composit":
            embedders[k] = CompositeEmbedder(**v)
        else:
            embedders[k] = UserProvidedEmbedder(**v)

    return embedders


def _validate_file_type(file_path: Path) -> None:
    if file_path.suffix not in (".json", ".csv", ".ndjson"):
        raise MeilisearchError("File must be a json, ndjson, or csv file")


def _validate_ranking_score_threshold(ranking_score_threshold: float) -> None:
    if not 0.0 <= ranking_score_threshold <= 1.0:
        raise MeilisearchError("ranking_score_threshold must be between 0.0 and 1.0")
