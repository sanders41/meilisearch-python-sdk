from __future__ import annotations

from typing import Any, Sequence
from uuid import uuid4

import pytest

from meilisearch_python_sdk.errors import MeilisearchApiError
from meilisearch_python_sdk.models.search import FacetHits, FacetSearchResults, SearchResults
from meilisearch_python_sdk.plugins import Event, IndexPlugins
from meilisearch_python_sdk.types import JsonMapping


class DocumentPlugin:
    POST_EVENT = False
    PRE_EVENT = True

    def run_document_plugin(
        self,
        event: Event,
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
    POST_EVENT = True
    PRE_EVENT = False

    def run_post_search_plugin(
        self, event: Event, *, search_results: SearchResults | FacetSearchResults, **kwargs: Any
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
    POST_EVENT = True
    PRE_EVENT = False

    def run_plugin(self, event: Event, **kwargs: Any) -> None:
        print(f"Post plugin ran {kwargs}")  # noqa: T201


class PrePlugin:
    POST_EVENT = False
    PRE_EVENT = True

    def run_plugin(self, event: Event, **kwargs: Any) -> None:
        print(f"Pre plugin ran {kwargs}")  # noqa: T201


def test_add_documents(client, small_movies, capsys):
    plugins = IndexPlugins(add_documents_plugins=(PostPlugin(), PrePlugin()))
    index = client.create_index(str(uuid4()), plugins=plugins)
    response = index.add_documents(small_movies)
    update = client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"
    out, _ = capsys.readouterr()
    assert "Pre plugin ran {'documents':" in out
    assert "Post plugin ran {'result':" in out


def test_add_documents_in_batches(client, small_movies, capsys):
    plugins = IndexPlugins(add_documents_plugins=(PostPlugin(), PrePlugin()))
    index = client.create_index(str(uuid4()), plugins=plugins)
    response = index.add_documents_in_batches(small_movies, batch_size=100)
    for r in response:
        task = client.wait_for_task(r.task_uid)
        assert "succeeded" == task.status
    out, _ = capsys.readouterr()
    assert "Pre plugin ran {'documents':" in out
    assert "Post plugin ran {'result':" in out


def test_delete_document(client, small_movies, capsys):
    plugins = IndexPlugins(delete_document_plugins=(PostPlugin(), PrePlugin()))
    index = client.create_index(str(uuid4()), plugins=plugins)
    response = index.add_documents(small_movies)
    update = client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"

    response = index.delete_document("500682")
    out, _ = capsys.readouterr()

    assert "Pre plugin ran {'document_id':" in out
    assert "Post plugin ran {'result':" in out

    client.wait_for_task(response.task_uid)
    with pytest.raises(MeilisearchApiError):
        index.get_document("500682")


def test_delete_documents_by_filter(client, small_movies, capsys):
    plugins = IndexPlugins(delete_documents_by_filter_plugins=(PostPlugin(), PrePlugin()))
    index = client.create_index(str(uuid4()), plugins=plugins)
    response = index.update_filterable_attributes(["genre"])
    client.wait_for_task(response.task_uid)
    response = index.add_documents(small_movies)
    update = client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"

    response = index.get_documents()
    assert "action" in ([x.get("genre") for x in response.results])
    response = index.delete_documents_by_filter("genre=action")

    out, _ = capsys.readouterr()

    assert "Pre plugin ran {'filter':" in out
    assert "Post plugin ran {'result':" in out

    client.wait_for_task(response.task_uid)
    response = index.get_documents()
    genres = [x.get("genre") for x in response.results]
    assert "action" not in genres
    assert "cartoon" in genres


def test_delete_documents(client, small_movies, capsys):
    plugins = IndexPlugins(delete_documents_plugins=(PostPlugin(), PrePlugin()))
    index = client.create_index(str(uuid4()), plugins=plugins)
    response = index.add_documents(small_movies)
    update = client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"

    to_delete = ["522681", "450465", "329996"]
    response = index.delete_documents(to_delete)
    client.wait_for_task(response.task_uid)
    out, _ = capsys.readouterr()

    assert "Pre plugin ran" in out
    assert "Post plugin ran {'result':" in out

    documents = index.get_documents()
    ids = [x["id"] for x in documents.results]
    assert to_delete not in ids


def test_delete_all_documents(client, small_movies, capsys):
    plugins = IndexPlugins(delete_all_documents_plugins=(PostPlugin(), PrePlugin()))
    index = client.create_index(str(uuid4()), plugins=plugins)
    response = index.add_documents(small_movies)
    update = client.wait_for_task(response.task_uid)
    update.status == "succeeded"

    response = index.delete_all_documents()
    client.wait_for_task(response.task_uid)
    out, _ = capsys.readouterr()

    assert "Pre plugin ran" in out
    assert "Post plugin ran {'result':" in out

    documents = index.get_documents()
    assert documents.results == []


def test_update_documents(client, small_movies, capsys):
    plugins = IndexPlugins(update_documents_plugins=(PostPlugin(), PrePlugin()))
    index = client.create_index(str(uuid4()), plugins=plugins)
    response = index.add_documents(small_movies)
    update = client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"

    response = index.get_documents()
    assert response.results[0]["title"] != "Some title"
    doc_id = response.results[0]["id"]
    response.results[0]["title"] = "Some title"
    update = index.update_documents([response.results[0]])
    out, _ = capsys.readouterr()
    client.wait_for_task(update.task_uid)
    response = index.get_document(doc_id)
    assert response["title"] == "Some title"
    assert "Pre plugin ran {'documents':" in out
    assert "Post plugin ran {'result':" in out


def test_update_documents_in_batches(client, small_movies, capsys):
    plugins = IndexPlugins(update_documents_plugins=(PostPlugin(), PrePlugin()))
    index = client.create_index(str(uuid4()), plugins=plugins)
    response = index.add_documents(small_movies)
    update = client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"

    response = index.get_documents()
    assert response.results[0]["title"] != "Some title"
    doc_id = response.results[0]["id"]
    response.results[0]["title"] = "Some title"
    update = index.update_documents_in_batches([response.results[0]], batch_size=100)
    out, _ = capsys.readouterr()
    for u in update:
        task = client.wait_for_task(u.task_uid)
        assert "succeeded" == task.status
    response = index.get_document(doc_id)
    assert response["title"] == "Some title"
    assert "Pre plugin ran {'documents':" in out
    assert "Post plugin ran {'result':" in out


def test_search(client, small_movies, capsys):
    plugins = IndexPlugins(search_plugins=(PostPlugin(), PrePlugin()))
    index = client.create_index(str(uuid4()), plugins=plugins)
    response = index.add_documents(small_movies)
    client.wait_for_task(response.task_uid)
    response = index.search("How to Train Your Dragon")
    assert response.hits[0]["id"] == "166428"
    assert "_formatted" not in response.hits[0]

    out, _ = capsys.readouterr()

    assert "Pre plugin ran {'query':" in out
    assert "Post plugin ran {'search_results':" in out


def test_facet_search(client, small_movies, capsys):
    plugins = IndexPlugins(search_plugins=(PostPlugin(), PrePlugin()))
    index = client.create_index(str(uuid4()), plugins=plugins)
    update = index.update_filterable_attributes(["genre"])
    client.wait_for_task(update.task_uid)
    response = index.add_documents(small_movies)
    client.wait_for_task(response.task_uid)
    response = index.facet_search(
        "How to Train Your Dragon", facet_name="genre", facet_query="cartoon"
    )
    assert response.facet_hits[0].value == "cartoon"
    assert response.facet_hits[0].count == 1

    out, _ = capsys.readouterr()

    assert "Pre plugin ran {'query':" in out
    assert "Post plugin ran {'search_results':" in out


def test_documents_plugin(client, small_movies):
    plugins = IndexPlugins(add_documents_plugins=(DocumentPlugin(),))
    index = client.create_index(str(uuid4()), plugins=plugins)
    response = index.add_documents(small_movies)
    update = client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"
    result = index.search("")
    assert len(result.hits) == 1
    assert result.hits[0]["title"] == "Test"


def test_search_plugin(client, small_movies):
    plugins = IndexPlugins(search_plugins=(SearchPlugin(),))
    index = client.create_index(str(uuid4()), plugins=plugins)
    response = index.add_documents(small_movies)
    update = client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"
    result = index.search("")
    assert len(result.hits) == 1
    assert result.hits[0]["title"] == "Test"


def test_facet_search_plugin(client, small_movies):
    plugins = IndexPlugins(search_plugins=(SearchPlugin(),))
    index = client.create_index(str(uuid4()), plugins=plugins)
    response = index.update_filterable_attributes(["genre"])
    update = client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"
    response = index.add_documents(small_movies)
    update = client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"
    result = index.facet_search("", facet_name="genre", facet_query="cartoon")
    assert len(result.facet_hits) == 1
    assert result.facet_hits[0].value == "Test"
