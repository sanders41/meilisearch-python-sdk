from __future__ import annotations

import asyncio
from collections.abc import Sequence
from copy import deepcopy
from datetime import datetime
from typing import Any
from uuid import uuid4

import pytest

from meilisearch_python_sdk.errors import MeilisearchApiError
from meilisearch_python_sdk.models.search import FacetSearchResults, SearchResults
from meilisearch_python_sdk.models.task import TaskInfo
from meilisearch_python_sdk.plugins import AsyncEvent, AsyncIndexPlugins
from meilisearch_python_sdk.types import JsonMapping


class ConcurrentPlugin:
    CONCURRENT_EVENT = True
    POST_EVENT = False
    PRE_EVENT = False

    async def run_plugin(self, event: AsyncEvent, **kwargs: Any) -> None:
        print(f"Concurrent plugin ran {kwargs}")  # noqa: T201


class DocumentPlugin:
    CONCURRENT_EVENT = True
    POST_EVENT = True
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
        search_results: SearchResults,
        **kwargs: Any,
    ) -> SearchResults | None:
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

        return search_results


class FacetSearchPlugin:
    CONCURRENT_EVENT = False
    POST_EVENT = True
    PRE_EVENT = False

    async def run_plugin(
        self,
        event: AsyncEvent,
        **kwargs: Any,
    ) -> FacetSearchResults | None:
        if (
            kwargs.get("result")
            and isinstance(kwargs["result"], FacetSearchResults)
            and kwargs["result"].facet_hits
        ):
            kwargs["result"].facet_hits[0].value = "test"
            return kwargs["result"]

        return None


class PostPlugin:
    CONCURRENT_EVENT = False
    POST_EVENT = True
    PRE_EVENT = False

    async def run_plugin(self, event: AsyncEvent, **kwargs: Any) -> None:
        print(f"Post plugin ran {kwargs}")  # noqa: T201


class TaskInfoPlugin:
    CONCURRENT_EVENT = False
    POST_EVENT = True
    PRE_EVENT = False

    async def run_plugin(self, event: AsyncEvent, **kwargs: Any) -> TaskInfo:
        return TaskInfo(
            task_uid=1,
            status="succeeded",
            type="test",
            task_type="test",
            enqueued_at=datetime.now(),
        )


class PrePlugin:
    CONCURRENT_EVENT = False
    POST_EVENT = False
    PRE_EVENT = True

    async def run_plugin(self, event: AsyncEvent, **kwargs: Any) -> None:
        print(f"Pre plugin ran {kwargs}")  # noqa: T201


@pytest.mark.parametrize(
    "plugins, expected",
    (
        ((ConcurrentPlugin(),), ("Concurrent plugin ran",)),
        ((PostPlugin(),), ("Post plugin ran",)),
        ((PrePlugin(),), ("Pre plugin ran")),
        (
            (ConcurrentPlugin(), PostPlugin(), PrePlugin()),
            ("Concurrent plugin ran", "Post plugin ran", "Pre plugin ran"),
        ),
    ),
)
async def test_add_documents(plugins, expected, async_client, small_movies, capsys):
    use_plugins = AsyncIndexPlugins(add_documents_plugins=plugins)
    index = await async_client.create_index(str(uuid4()), plugins=use_plugins)
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"
    out, _ = capsys.readouterr()
    for e in expected:
        assert e in out


async def test_add_documents_in_batches(async_client, small_movies, capsys):
    use_plugins = AsyncIndexPlugins(
        add_documents_plugins=(ConcurrentPlugin(), PostPlugin(), PrePlugin())
    )
    index = await async_client.create_index(str(uuid4()), plugins=use_plugins)
    response = await index.add_documents_in_batches(small_movies, batch_size=100)
    tasks = await asyncio.gather(*[async_client.wait_for_task(x.task_uid) for x in response])
    assert {"succeeded"} == {x.status for x in tasks}
    out, _ = capsys.readouterr()
    assert "Concurrent plugin ran {'documents':" in out
    assert "Pre plugin ran {'documents':" in out
    assert "Post plugin ran {'result':" in out


@pytest.mark.parametrize(
    "plugins, expected",
    (
        ((ConcurrentPlugin(),), ("Concurrent plugin ran",)),
        ((PostPlugin(),), ("Post plugin ran",)),
        ((PrePlugin(),), ("Pre plugin ran")),
        (
            (ConcurrentPlugin(), PostPlugin(), PrePlugin()),
            ("Concurrent plugin ran", "Post plugin ran", "Pre plugin ran"),
        ),
    ),
)
async def test_delete_document(plugins, expected, async_client, small_movies, capsys):
    use_plugins = AsyncIndexPlugins(delete_document_plugins=(plugins))
    index = await async_client.create_index(str(uuid4()), plugins=use_plugins)
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"

    response = await index.delete_document("500682")
    out, _ = capsys.readouterr()

    for e in expected:
        assert e in out

    await async_client.wait_for_task(response.task_uid)
    with pytest.raises(MeilisearchApiError):
        await index.get_document("500682")


@pytest.mark.parametrize(
    "plugins, expected",
    (
        ((ConcurrentPlugin(),), ("Concurrent plugin ran",)),
        ((PostPlugin(),), ("Post plugin ran",)),
        ((PrePlugin(),), ("Pre plugin ran")),
        (
            (ConcurrentPlugin(), PostPlugin(), PrePlugin()),
            ("Concurrent plugin ran", "Post plugin ran", "Pre plugin ran"),
        ),
    ),
)
async def test_delete_documents_by_filter(plugins, expected, async_client, small_movies, capsys):
    use_plugins = AsyncIndexPlugins(delete_documents_by_filter_plugins=plugins)
    index = await async_client.create_index(str(uuid4()), plugins=use_plugins)
    response = await index.update_filterable_attributes(["genre"])
    await async_client.wait_for_task(response.task_uid)
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"

    response = await index.get_documents()
    assert "action" in ([x.get("genre") for x in response.results])
    response = await index.delete_documents_by_filter("genre=action")

    out, _ = capsys.readouterr()

    for e in expected:
        assert e in out

    await async_client.wait_for_task(response.task_uid)
    response = await index.get_documents()
    genres = [x.get("genre") for x in response.results]
    assert "action" not in genres
    assert "cartoon" in genres


@pytest.mark.parametrize(
    "plugins, expected",
    (
        ((ConcurrentPlugin(),), ("Concurrent plugin ran",)),
        ((PostPlugin(),), ("Post plugin ran",)),
        ((PrePlugin(),), ("Pre plugin ran")),
        (
            (ConcurrentPlugin(), PostPlugin(), PrePlugin()),
            ("Concurrent plugin ran", "Post plugin ran", "Pre plugin ran"),
        ),
    ),
)
async def test_delete_documents(plugins, expected, async_client, small_movies, capsys):
    use_plugins = AsyncIndexPlugins(delete_documents_plugins=plugins)
    index = await async_client.create_index(str(uuid4()), plugins=use_plugins)
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"

    to_delete = ["522681", "450465", "329996"]
    response = await index.delete_documents(to_delete)
    await async_client.wait_for_task(response.task_uid)
    out, _ = capsys.readouterr()

    for e in expected:
        assert e in out

    documents = await index.get_documents()
    ids = [x["id"] for x in documents.results]
    assert to_delete not in ids


@pytest.mark.parametrize(
    "plugins, expected",
    (
        ((ConcurrentPlugin(),), ("Concurrent plugin ran",)),
        ((PostPlugin(),), ("Post plugin ran",)),
        ((PrePlugin(),), ("Pre plugin ran")),
        (
            (ConcurrentPlugin(), PostPlugin(), PrePlugin()),
            ("Concurrent plugin ran", "Post plugin ran", "Pre plugin ran"),
        ),
    ),
)
async def test_delete_all_documents(plugins, expected, async_client, small_movies, capsys):
    use_plugins = AsyncIndexPlugins(delete_all_documents_plugins=plugins)
    index = await async_client.create_index(str(uuid4()), plugins=use_plugins)
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"

    response = await index.delete_all_documents()
    await async_client.wait_for_task(response.task_uid)
    out, _ = capsys.readouterr()

    for e in expected:
        assert e in out

    documents = await index.get_documents()
    assert documents.results == []


@pytest.mark.parametrize(
    "plugins, expected",
    (
        ((ConcurrentPlugin(),), ("Concurrent plugin ran",)),
        ((PostPlugin(),), ("Post plugin ran",)),
        ((PrePlugin(),), ("Pre plugin ran")),
        (
            (ConcurrentPlugin(), PostPlugin(), PrePlugin()),
            ("Concurrent plugin ran", "Post plugin ran", "Pre plugin ran"),
        ),
    ),
)
async def test_update_documents(plugins, expected, async_client, small_movies, capsys):
    use_plugins = AsyncIndexPlugins(update_documents_plugins=plugins)
    index = await async_client.create_index(str(uuid4()), plugins=use_plugins)
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"

    response = await index.get_documents()
    assert response.results[0]["title"] != "Some title"
    doc_id = response.results[0]["id"]
    response.results[0]["title"] = "Some title"
    update = await index.update_documents([response.results[0]])
    out, _ = capsys.readouterr()
    await async_client.wait_for_task(update.task_uid)
    response = await index.get_document(doc_id)
    assert response["title"] == "Some title"

    for e in expected:
        assert e in out


async def test_update_documents_in_batches(async_client, small_movies, capsys):
    plugins = AsyncIndexPlugins(
        update_documents_plugins=(ConcurrentPlugin(), PostPlugin(), PrePlugin())
    )
    index = await async_client.create_index(str(uuid4()), plugins=plugins)
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"
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


@pytest.mark.parametrize(
    "plugins, expected",
    (
        ((ConcurrentPlugin(),), ("Concurrent plugin ran",)),
        ((PostPlugin(),), ("Post plugin ran",)),
        ((PrePlugin(),), ("Pre plugin ran")),
        (
            (ConcurrentPlugin(), PostPlugin(), PrePlugin()),
            ("Concurrent plugin ran", "Post plugin ran", "Pre plugin ran"),
        ),
    ),
)
async def test_facet_search(plugins, expected, async_client, small_movies, capsys):
    use_plugins = AsyncIndexPlugins(facet_search_plugins=plugins)
    index = await async_client.create_index(str(uuid4()), plugins=use_plugins)
    update = await index.update_filterable_attributes(["genre"])
    response = await index.add_documents(small_movies)
    await async_client.wait_for_task(response.task_uid)
    await async_client.wait_for_task(update.task_uid)
    response = await index.facet_search(
        "How to Train Your Dragon", facet_name="genre", facet_query="cartoon"
    )
    assert response.facet_hits[0].value == "cartoon"
    assert response.facet_hits[0].count == 1
    out, _ = capsys.readouterr()
    for e in expected:
        assert e in out


@pytest.mark.parametrize(
    "plugins",
    (
        (FacetSearchPlugin(),),
        (
            ConcurrentPlugin(),
            FacetSearchPlugin(),
        ),
    ),
)
async def test_facet_search_return(plugins, async_client, small_movies):
    plugins = AsyncIndexPlugins(facet_search_plugins=plugins)
    index = await async_client.create_index(str(uuid4()), plugins=plugins)
    update = await index.update_filterable_attributes(["genre"])
    response = await index.add_documents(small_movies)
    await async_client.wait_for_task(response.task_uid)
    await async_client.wait_for_task(update.task_uid)
    response = await index.facet_search(
        "How to Train Your Dragon", facet_name="genre", facet_query="cartoon"
    )
    assert response.facet_hits[0].value == "test"


@pytest.mark.parametrize(
    "plugins, expected",
    (
        ((ConcurrentPlugin(),), ("Concurrent plugin ran",)),
        ((PostPlugin(),), ("Post plugin ran",)),
        ((PrePlugin(),), ("Pre plugin ran")),
        (
            (ConcurrentPlugin(), PostPlugin(), PrePlugin()),
            ("Concurrent plugin ran", "Post plugin ran", "Pre plugin ran"),
        ),
    ),
)
async def test_search(plugins, expected, async_client, small_movies, capsys):
    use_plugins = AsyncIndexPlugins(search_plugins=plugins)
    index = await async_client.create_index(str(uuid4()), plugins=use_plugins)
    response = await index.add_documents(small_movies)
    await async_client.wait_for_task(response.task_uid)
    response = await index.search("How to Train Your Dragon")
    assert response.hits[0]["id"] == "166428"
    assert "_formatted" not in response.hits[0]

    out, _ = capsys.readouterr()

    for e in expected:
        assert e in out


@pytest.mark.parametrize("plugins", ((DocumentPlugin(),), (DocumentPlugin(), ConcurrentPlugin())))
async def test_add_documents_plugin(plugins, async_client, small_movies):
    use_plugins = AsyncIndexPlugins(add_documents_plugins=plugins)
    index = await async_client.create_index(str(uuid4()), plugins=use_plugins)
    response = await index.add_documents(small_movies)
    task = await async_client.wait_for_task(response.task_uid)
    assert task.status == "succeeded"
    result = await index.search("")
    assert len(result.hits) == 1
    assert result.hits[0]["title"] == "Test"


@pytest.mark.parametrize("plugins", ((DocumentPlugin(),), (DocumentPlugin(), ConcurrentPlugin())))
async def test_update_documents_plugin(plugins, async_client, small_movies):
    use_plugins = AsyncIndexPlugins(update_documents_plugins=plugins)
    index = await async_client.create_index(str(uuid4()), plugins=use_plugins)
    response = await index.add_documents(small_movies)
    task = await async_client.wait_for_task(response.task_uid)
    assert task.status == "succeeded"
    doc = deepcopy(small_movies[0])
    doc["title"] = "Test"
    update = await index.update_documents([doc])
    await async_client.wait_for_task(update.task_uid)
    result = await index.get_document(1)
    assert result["title"] == "Test"


@pytest.mark.parametrize("plugins", ((SearchPlugin(),), (SearchPlugin(), ConcurrentPlugin())))
async def test_search_plugin(plugins, async_client, small_movies):
    use_plugins = AsyncIndexPlugins(search_plugins=plugins)
    index = await async_client.create_index(str(uuid4()), plugins=use_plugins)
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"
    result = await index.search("")
    assert len(result.hits) == 1
    assert result.hits[0]["title"] == "Test"


@pytest.mark.parametrize("plugins", ((TaskInfoPlugin(),), (TaskInfoPlugin(), ConcurrentPlugin())))
async def test_add_documents_task_info(plugins, async_client, small_movies):
    use_plugins = AsyncIndexPlugins(add_documents_plugins=plugins)
    index = await async_client.create_index(str(uuid4()), plugins=use_plugins)
    task = await index.add_documents(small_movies)
    assert task.task_uid == 1


@pytest.mark.parametrize("plugins", ((TaskInfoPlugin(),), (TaskInfoPlugin(), ConcurrentPlugin())))
async def test_delete_document_task_info(plugins, async_client, small_movies):
    use_plugins = AsyncIndexPlugins(delete_document_plugins=plugins)
    index = await async_client.create_index(str(uuid4()), plugins=use_plugins)
    task = await index.add_documents(small_movies)
    await async_client.wait_for_task(task.task_uid)
    task = await index.delete_document(small_movies[0]["id"])
    assert task.task_uid == 1


@pytest.mark.parametrize("plugins", ((TaskInfoPlugin(),), (TaskInfoPlugin(), ConcurrentPlugin())))
async def test_delete_documents_task_info(plugins, async_client, small_movies):
    use_plugins = AsyncIndexPlugins(delete_documents_plugins=plugins)
    index = await async_client.create_index(str(uuid4()), plugins=use_plugins)
    task = await index.add_documents(small_movies)
    await async_client.wait_for_task(task.task_uid)
    task = await index.delete_documents([small_movies[0]["id"], small_movies[1]["id"]])
    assert task.task_uid == 1


@pytest.mark.parametrize("plugins", ((TaskInfoPlugin(),), (TaskInfoPlugin(), ConcurrentPlugin())))
async def test_delete_all_documents_task_info(plugins, async_client, small_movies):
    use_plugins = AsyncIndexPlugins(delete_all_documents_plugins=plugins)
    index = await async_client.create_index(str(uuid4()), plugins=use_plugins)
    task = await index.add_documents(small_movies)
    await async_client.wait_for_task(task.task_uid)
    task = await index.delete_all_documents()
    assert task.task_uid == 1


@pytest.mark.parametrize("plugins", ((TaskInfoPlugin(),), (TaskInfoPlugin(), ConcurrentPlugin())))
async def test_delete_documents_by_filter_task_info(plugins, async_client, small_movies):
    use_plugins = AsyncIndexPlugins(delete_documents_by_filter_plugins=plugins)
    index = await async_client.create_index(str(uuid4()), plugins=use_plugins)
    response = await index.update_filterable_attributes(["genre"])
    await async_client.wait_for_task(response.task_uid)
    task = await index.add_documents(small_movies)
    await async_client.wait_for_task(task.task_uid)
    task = await index.delete_documents_by_filter("genre=action")
    assert task.task_uid == 1


@pytest.mark.parametrize("plugins", ((TaskInfoPlugin(),), (TaskInfoPlugin(), ConcurrentPlugin())))
async def test_update_documents_task_info(plugins, async_client, small_movies):
    use_plugins = AsyncIndexPlugins(update_documents_plugins=plugins)
    index = await async_client.create_index(str(uuid4()), plugins=use_plugins)
    task = await index.add_documents(small_movies)
    await async_client.wait_for_task(task.task_uid)
    doc = deepcopy(small_movies[0])
    doc["title"] = "test"
    task = await index.update_documents([doc])
    assert task.task_uid == 1
