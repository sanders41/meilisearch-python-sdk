import asyncio
from typing import Any, Sequence
from uuid import uuid4

import pytest

from meilisearch_python_sdk.errors import MeilisearchApiError
from meilisearch_python_sdk.models.search import FacetHits, FacetSearchResults, SearchResults
from meilisearch_python_sdk.plugins import AsyncEvent, AsyncIndexPlugins
from meilisearch_python_sdk.types import JsonMapping


class ConcurrentPlugin:
    CONCURRENT_EVENT = True
    POST_EVENT = False
    PRE_EVENT = False

    async def run_plugin(self, event: AsyncEvent, **kwargs: Any) -> None:
        print(f"Concurrent plugin ran {kwargs}")  # noqa: T201


class DocumentPlugin:
    CONCURRENT_EVENT = False
    POST_EVENT = False
    PRE_EVENT = True

    async def run_document_plugin(
        self,
        event: AsyncEvent,
        *,
        documents: Sequence[JsonMapping],
        primary_key: str | None,
        **kwargs: Any,
    ) -> Sequence[JsonMapping] | None:
        return [
            {
                "id": "1",
                "title": "Test",
                "poster": "https://image.tmdb.org/t/p/w1280/xnopI5Xtky18MPhK40cZAGAOVeV.jpg",
                "overview": "This is a test.",
                "release_date": 1553299200,
                "genre": "action",
            }
        ]


class SearchPlugin:
    CONCURRENT_EVENT = False
    POST_EVENT = True
    PRE_EVENT = False

    async def run_post_search_plugin(
        self,
        event: AsyncEvent,
        *,
        search_results: SearchResults | FacetSearchResults,
        **kwargs: Any,
    ) -> SearchResults | FacetSearchResults | None:
        if isinstance(search_results, SearchResults):
            search_results.hits = [
                {
                    "id": "1",
                    "title": "Test",
                    "poster": "https://image.tmdb.org/t/p/w1280/xnopI5Xtky18MPhK40cZAGAOVeV.jpg",
                    "overview": "This is a test.",
                    "release_date": 1553299200,
                    "genre": "action",
                }
            ]
        if isinstance(search_results, FacetSearchResults):
            search_results.facet_hits = [FacetHits(value="Test", count=1)]

        return search_results


class PostPlugin:
    CONCURRENT_EVENT = False
    POST_EVENT = True
    PRE_EVENT = False

    async def run_plugin(self, event: AsyncEvent, **kwargs: Any) -> None:
        print(f"Post plugin ran {kwargs}")  # noqa: T201


class PrePlugin:
    CONCURRENT_EVENT = False
    POST_EVENT = False
    PRE_EVENT = True

    async def run_plugin(self, event: AsyncEvent, **kwargs: Any) -> None:
        print(f"Pre plugin ran {kwargs}")  # noqa: T201


async def test_add_documents(async_client, small_movies, capsys):
    plugins = AsyncIndexPlugins(
        add_documents_plugins=(ConcurrentPlugin(), PostPlugin(), PrePlugin())
    )
    index = await async_client.create_index(str(uuid4()), plugins=plugins)
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"
    out, _ = capsys.readouterr()
    assert "Concurrent plugin ran {'documents':" in out
    assert "Pre plugin ran {'documents':" in out
    assert "Post plugin ran {'result':" in out


async def test_add_documents_in_batches(async_client, small_movies, capsys):
    plugins = AsyncIndexPlugins(
        add_documents_plugins=(ConcurrentPlugin(), PostPlugin(), PrePlugin())
    )
    index = await async_client.create_index(str(uuid4()), plugins=plugins)
    response = await index.add_documents_in_batches(small_movies, batch_size=100)
    tasks = await asyncio.gather(*[async_client.wait_for_task(x.task_uid) for x in response])
    assert {"succeeded"} == {x.status for x in tasks}
    out, _ = capsys.readouterr()
    assert "Concurrent plugin ran {'documents':" in out
    assert "Pre plugin ran {'documents':" in out
    assert "Post plugin ran {'result':" in out


async def test_delete_document(async_client, small_movies, capsys):
    plugins = AsyncIndexPlugins(
        delete_document_plugins=(ConcurrentPlugin(), PostPlugin(), PrePlugin())
    )
    index = await async_client.create_index(str(uuid4()), plugins=plugins)
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"

    out, _ = capsys.readouterr()

    response = await index.delete_document("500682")
    out, _ = capsys.readouterr()

    assert "Concurrent plugin ran {'document_id':" in out
    assert "Pre plugin ran {'document_id':" in out
    assert "Post plugin ran {'result':" in out

    await async_client.wait_for_task(response.task_uid)
    with pytest.raises(MeilisearchApiError):
        await index.get_document("500682")


async def test_delete_documents_by_filter(async_client, small_movies, capsys):
    plugins = AsyncIndexPlugins(
        delete_documents_by_filter_plugins=(ConcurrentPlugin(), PostPlugin(), PrePlugin())
    )
    index = await async_client.create_index(str(uuid4()), plugins=plugins)
    response = await index.update_filterable_attributes(["genre"])
    await async_client.wait_for_task(response.task_uid)
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"

    out, _ = capsys.readouterr()

    response = await index.get_documents()
    assert "action" in ([x.get("genre") for x in response.results])
    response = await index.delete_documents_by_filter("genre=action")

    out, _ = capsys.readouterr()

    assert "Concurrent plugin ran {'filter':" in out
    assert "Pre plugin ran {'filter':" in out
    assert "Post plugin ran {'result':" in out

    await async_client.wait_for_task(response.task_uid)
    response = await index.get_documents()
    genres = [x.get("genre") for x in response.results]
    assert "action" not in genres
    assert "cartoon" in genres


async def test_delete_documents(async_client, small_movies, capsys):
    plugins = AsyncIndexPlugins(
        delete_documents_plugins=(ConcurrentPlugin(), PostPlugin(), PrePlugin())
    )
    index = await async_client.create_index(str(uuid4()), plugins=plugins)
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"

    out, _ = capsys.readouterr()

    to_delete = ["522681", "450465", "329996"]
    response = await index.delete_documents(to_delete)
    await async_client.wait_for_task(response.task_uid)
    out, _ = capsys.readouterr()

    assert "Concurrent plugin ran" in out
    assert "Pre plugin ran" in out
    assert "Post plugin ran {'result':" in out

    documents = await index.get_documents()
    ids = [x["id"] for x in documents.results]
    assert to_delete not in ids


async def test_update_documents(async_client, small_movies, capsys):
    plugins = AsyncIndexPlugins(
        update_documents_plugins=(ConcurrentPlugin(), PostPlugin(), PrePlugin())
    )
    index = await async_client.create_index(str(uuid4()), plugins=plugins)
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"

    out, _ = capsys.readouterr()

    response = await index.get_documents()
    assert response.results[0]["title"] != "Some title"
    doc_id = response.results[0]["id"]
    response.results[0]["title"] = "Some title"
    update = await index.update_documents([response.results[0]])
    out, _ = capsys.readouterr()
    await async_client.wait_for_task(update.task_uid)
    response = await index.get_document(doc_id)
    assert response["title"] == "Some title"
    assert "Concurrent plugin ran {'documents':" in out
    assert "Pre plugin ran {'documents':" in out
    assert "Post plugin ran {'result':" in out


async def test_update_documents_in_batches(async_client, small_movies, capsys):
    plugins = AsyncIndexPlugins(
        update_documents_plugins=(ConcurrentPlugin(), PostPlugin(), PrePlugin())
    )
    index = await async_client.create_index(str(uuid4()), plugins=plugins)
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"

    out, _ = capsys.readouterr()

    response = await index.get_documents()
    assert response.results[0]["title"] != "Some title"
    doc_id = response.results[0]["id"]
    response.results[0]["title"] = "Some title"
    update = await index.update_documents_in_batches([response.results[0]], batch_size=100)
    out, _ = capsys.readouterr()
    tasks = await asyncio.gather(*[async_client.wait_for_task(x.task_uid) for x in update])
    assert {"succeeded"} == {x.status for x in tasks}
    response = await index.get_document(doc_id)
    assert response["title"] == "Some title"
    assert "Concurrent plugin ran {'documents':" in out
    assert "Pre plugin ran {'documents':" in out
    assert "Post plugin ran {'result':" in out


async def test_search(async_client, small_movies, capsys):
    plugins = AsyncIndexPlugins(search_plugins=(ConcurrentPlugin(), PostPlugin(), PrePlugin()))
    index = await async_client.create_index(str(uuid4()), plugins=plugins)
    response = await index.add_documents(small_movies)
    await async_client.wait_for_task(response.task_uid)
    out, _ = capsys.readouterr()

    response = await index.search("How to Train Your Dragon")
    assert response.hits[0]["id"] == "166428"
    assert "_formatted" not in response.hits[0]

    out, _ = capsys.readouterr()

    assert "Concurrent plugin ran {'query':" in out
    assert "Pre plugin ran {'query':" in out
    assert "Post plugin ran {'search_results':" in out


async def test_facet_search(async_client, small_movies, capsys):
    plugins = AsyncIndexPlugins(search_plugins=(ConcurrentPlugin(), PostPlugin(), PrePlugin()))
    index = await async_client.create_index(str(uuid4()), plugins=plugins)
    update = await index.update_filterable_attributes(["genre"])
    response = await index.add_documents(small_movies)
    await async_client.wait_for_task(response.task_uid)
    out, _ = capsys.readouterr()

    await async_client.wait_for_task(update.task_uid)
    response = await index.facet_search(
        "How to Train Your Dragon", facet_name="genre", facet_query="cartoon"
    )
    assert response.facet_hits[0].value == "cartoon"
    assert response.facet_hits[0].count == 1

    out, _ = capsys.readouterr()

    assert "Concurrent plugin ran {'query':" in out
    assert "Pre plugin ran {'query':" in out
    assert "Post plugin ran {'search_results':" in out


async def test_documents_plugin(async_client, small_movies):
    plugins = AsyncIndexPlugins(add_documents_plugins=(DocumentPlugin(),))
    index = await async_client.create_index(str(uuid4()), plugins=plugins)
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"
    result = await index.search("")
    assert len(result.hits) == 1
    assert result.hits[0]["title"] == "Test"


async def test_search_plugin(async_client, small_movies):
    plugins = AsyncIndexPlugins(search_plugins=(SearchPlugin(),))
    index = await async_client.create_index(str(uuid4()), plugins=plugins)
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"
    result = await index.search("")
    assert len(result.hits) == 1
    assert result.hits[0]["title"] == "Test"


async def test_facet_search_plugin(async_client, small_movies):
    plugins = AsyncIndexPlugins(search_plugins=(SearchPlugin(),))
    index = await async_client.create_index(str(uuid4()), plugins=plugins)
    response = await index.update_filterable_attributes(["genre"])
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"
    assert update.status == "succeeded"
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"
    result = await index.facet_search("", facet_name="genre", facet_query="cartoon")
    assert len(result.facet_hits) == 1
    assert result.facet_hits[0].value == "Test"
