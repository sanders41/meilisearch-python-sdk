from uuid import uuid4

from examples.orjson_example import add_documents as orjson_add_documents
from examples.search_tracker import SearchTrackerPlugin, search
from examples.search_tracker import add_documents as search_tracker_add_documents
from examples.ujson_example import add_documents as ujson_add_documents
from examples.update_settings import add_documents as update_settings_add_documents
from examples.update_settings import update_settings
from meilisearch_python_sdk.plugins import IndexPlugins


def test_orjson_example(small_movies_path, client):
    task = orjson_add_documents(small_movies_path)
    client.wait_for_task(task.task_uid)
    result = client.get_task(task.task_uid)
    assert result.status == "succeeded"


def test_search_tracker(small_movies_path, client, tmp_path):
    db_path = tmp_path / "search_tracker.db"
    plugins = IndexPlugins(search_plugins=(SearchTrackerPlugin(db_path),))
    index = client.create_index(
        uid=str(uuid4()), primary_key="id", plugins=plugins, timeout_in_ms=5000
    )
    task = search_tracker_add_documents(index, small_movies_path)
    client.wait_for_task(task.task_uid)
    result = client.get_task(task.task_uid)
    assert result.status == "succeeded"
    result = search(index, "Cars")
    assert len(result.hits) > 0


def test_update_settings(small_movies_path, empty_index, client):
    index = empty_index()
    task = update_settings(index)
    client.wait_for_task(task.task_uid)
    task = update_settings_add_documents(index, small_movies_path)
    client.wait_for_task(task.task_uid)
    result = client.get_task(task.task_uid)
    assert result.status == "succeeded"


def test_ujson_example(small_movies_path, client):
    task = ujson_add_documents(small_movies_path)
    client.wait_for_task(task.task_uid)
    result = client.get_task(task.task_uid)
    assert result.status == "succeeded"
