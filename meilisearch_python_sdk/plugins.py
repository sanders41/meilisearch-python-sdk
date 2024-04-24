from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, NamedTuple, Protocol, Sequence

if TYPE_CHECKING:  # pragma: no cover
    from meilisearch_python_sdk.models.search import FacetSearchResults, SearchResults
    from meilisearch_python_sdk.models.task import TaskInfo
    from meilisearch_python_sdk.types import JsonDict, JsonMapping


class AsyncEvent(Enum):
    PRE = "pre"
    CONCURRENT = "concurrent"
    POST = "post"


class Event(Enum):
    PRE = "pre"
    POST = "post"


class AsyncPlugin(Protocol):
    CONCURRENT_EVENT: bool
    POST_EVENT: bool
    PRE_EVENT: bool

    async def run_plugin(
        self, event: AsyncEvent, **kwargs: Any
    ) -> (
        None | list[JsonDict] | TaskInfo | list[TaskInfo] | SearchResults | FacetSearchResults
    ):  # pragma: no cover
        ...


class AsyncDocumentPlugin(Protocol):
    CONCURRENT_EVENT: bool
    POST_EVENT: bool
    PRE_EVENT: bool

    async def run_document_plugin(
        self,
        event: AsyncEvent,
        *,
        documents: Sequence[JsonMapping],
        primary_key: str | None,
        **kwargs: Any,
    ) -> Sequence[JsonMapping] | None:  # pragma: no cover
        ...


class AsyncPostSearchPlugin(Protocol):
    CONCURRENT_EVENT: bool
    POST_EVENT: bool
    PRE_EVENT: bool

    async def run_post_search_plugin(
        self,
        event: AsyncEvent,
        *,
        search_results: SearchResults,
        **kwargs: Any,
    ) -> SearchResults | None:  # pragma: no cover
        ...


class Plugin(Protocol):
    POST_EVENT: bool
    PRE_EVENT: bool

    def run_plugin(
        self, event: Event, **kwargs: Any
    ) -> (
        None | list[JsonDict] | TaskInfo | list[TaskInfo] | SearchResults | FacetSearchResults
    ):  # pragma: no cover
        ...


class DocumentPlugin(Protocol):
    POST_EVENT: bool
    PRE_EVENT: bool

    def run_document_plugin(
        self,
        event: Event,
        *,
        documents: Sequence[JsonMapping],
        primary_key: str | None,
        **kwargs: Any,
    ) -> Sequence[JsonMapping] | None:  # pragma: no cover
        ...


class PostSearchPlugin(Protocol):
    POST_EVENT: bool
    PRE_EVENT: bool

    def run_post_search_plugin(
        self, event: Event, *, search_results: SearchResults, **kwargs: Any
    ) -> SearchResults | None:  # pragma: no cover
        ...


class AsyncIndexPlugins(NamedTuple):
    add_documents_plugins: Sequence[AsyncPlugin | AsyncDocumentPlugin] | None = None
    delete_all_documents_plugins: Sequence[AsyncPlugin] | None = None
    delete_document_plugins: Sequence[AsyncPlugin] | None = None
    delete_documents_plugins: Sequence[AsyncPlugin] | None = None
    delete_documents_by_filter_plugins: Sequence[AsyncPlugin] | None = None
    facet_search_plugins: Sequence[AsyncPlugin] | None = None
    search_plugins: Sequence[AsyncPlugin | AsyncPostSearchPlugin] | None = None
    update_documents_plugins: Sequence[AsyncPlugin | AsyncDocumentPlugin] | None = None


class IndexPlugins(NamedTuple):
    add_documents_plugins: Sequence[Plugin | DocumentPlugin] | None = None
    delete_all_documents_plugins: Sequence[Plugin] | None = None
    delete_document_plugins: Sequence[Plugin] | None = None
    delete_documents_plugins: Sequence[Plugin] | None = None
    delete_documents_by_filter_plugins: Sequence[Plugin] | None = None
    facet_search_plugins: Sequence[Plugin] | None = None
    search_plugins: Sequence[Plugin | PostSearchPlugin] | None = None
    update_documents_plugins: Sequence[Plugin | DocumentPlugin] | None = None
