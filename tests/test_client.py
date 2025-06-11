from __future__ import annotations

from datetime import datetime, timedelta, timezone
from time import sleep
from urllib.parse import quote_plus
from uuid import uuid4

import jwt
import pytest
from httpx import Client as HttpxClient
from httpx import ConnectError, ConnectTimeout, RemoteProtocolError, Request, Response

from meilisearch_python_sdk import Client
from meilisearch_python_sdk.errors import (
    BatchNotFoundError,
    InvalidRestriction,
    MeilisearchApiError,
    MeilisearchCommunicationError,
    MeilisearchTaskFailedError,
    MeilisearchTimeoutError,
)
from meilisearch_python_sdk.models.client import KeyCreate, KeyUpdate, Network
from meilisearch_python_sdk.models.index import IndexInfo
from meilisearch_python_sdk.models.version import Version
from meilisearch_python_sdk.types import JsonDict


@pytest.fixture
def test_key(client):
    key_info = KeyCreate(description="test", actions=["search"], indexes=["movies"])
    key = client.create_key(key_info)

    yield key

    try:
        client.delete_key(key.key)
    except MeilisearchApiError:
        pass


@pytest.fixture
def test_key_info(client):
    key_info = KeyCreate(description="test", actions=["search"], indexes=["movies"])

    yield key_info

    try:
        keys = client.get_keys()
        key = next(x for x in keys.results if x.description == key_info.description)
        client.delete_key(key.key)
    except MeilisearchApiError:
        pass


def wait_for_dump_creation(client, dump_uid, timeout_in_ms=10000.0, interval_in_ms=500.0):
    start_time = datetime.now()
    elapsed_time = 0.0
    while elapsed_time < timeout_in_ms:
        dump = client.get_dump_status(dump_uid)
        if dump.status != "in_progress":
            return None
        sleep(interval_in_ms / 1000)
        time_delta = datetime.now() - start_time
        elapsed_time = time_delta.seconds * 1000 + time_delta.microseconds / 1000
    raise TimeoutError


@pytest.mark.parametrize(
    "api_key, custom_headers, expected",
    (
        ("testKey", None, {"Authorization": "Bearer testKey"}),
        (
            "testKey",
            {"header_key_1": "header_value_1", "header_key_2": "header_value_2"},
            {
                "Authorization": "Bearer testKey",
                "header_key_1": "header_value_1",
                "header_key_2": "header_value_2",
            },
        ),
        (
            None,
            {"header_key_1": "header_value_1", "header_key_2": "header_value_2"},
            {
                "header_key_1": "header_value_1",
                "header_key_2": "header_value_2",
            },
        ),
        (None, None, None),
    ),
)
def test_headers(api_key, custom_headers, expected, ssl_verify):
    client = Client(
        "https://127.0.0.1:7700", api_key=api_key, custom_headers=custom_headers, verify=ssl_verify
    )

    assert client._headers == expected


def test_create_index_with_primary_key(client):
    uid = str(uuid4())
    primary_key = "pk_test"
    index = client.create_index(uid=uid, primary_key=primary_key)

    assert index.uid == uid

    assert index.primary_key == primary_key
    assert isinstance(index.created_at, datetime)
    assert isinstance(index.updated_at, datetime)


def test_create_index_no_primary_key(client):
    uid = str(uuid4())
    index = client.create_index(uid=uid)

    assert index.uid == uid

    assert index.primary_key is None
    assert isinstance(index.created_at, datetime)
    assert isinstance(index.updated_at, datetime)


def test_create_index_orjson_handler(client_orjson_handler):
    uid = str(uuid4())
    index = client_orjson_handler.create_index(uid=uid)

    assert index.uid == uid

    assert index.primary_key is None
    assert isinstance(index.created_at, datetime)
    assert isinstance(index.updated_at, datetime)


def test_create_index_ujson_handler(client_ujson_handler):
    uid = str(uuid4())
    index = client_ujson_handler.create_index(uid=uid)

    assert index.uid == uid

    assert index.primary_key is None
    assert isinstance(index.created_at, datetime)
    assert isinstance(index.updated_at, datetime)


def test_create_index_with_settings(client, new_settings):
    uid = str(uuid4())
    index = client.create_index(uid=uid, settings=new_settings)
    assert index.uid == uid
    response = index.get_settings()
    assert response.ranking_rules == new_settings.ranking_rules
    assert response.distinct_attribute is None
    assert response.searchable_attributes == new_settings.searchable_attributes
    assert response.displayed_attributes == ["*"]
    assert response.stop_words == []
    assert response.synonyms == {}
    assert response.sortable_attributes == new_settings.sortable_attributes
    assert response.typo_tolerance.enabled is False
    assert (
        response.faceting.max_values_per_facet == new_settings.faceting.max_values_per_facet == 123
    )
    assert response.pagination == new_settings.pagination
    assert response.separator_tokens == new_settings.separator_tokens
    assert response.non_separator_tokens == new_settings.non_separator_tokens
    assert response.dictionary == new_settings.dictionary


def test_create_index_with_settings_no_wait(client, new_settings):
    uid = str(uuid4())
    index = client.create_index(uid=uid, settings=new_settings, wait=False)
    assert index.uid == uid


@pytest.mark.no_parallel
def test_create_keys_with_wildcarded_actions(client, test_key_info):
    test_key_info.actions = ["documents.*"]
    key = client.create_key(test_key_info)

    assert key.actions == ["documents.*"]


@pytest.mark.no_parallel
def test_generate_tenant_token_custom_key(client, test_key):
    search_rules = {"test": "value"}
    expected = {"searchRules": search_rules, "apiKeyUid": test_key.uid}
    token = client.generate_tenant_token(search_rules, api_key=test_key)
    assert expected == jwt.decode(jwt=token, key=test_key.key, algorithms=["HS256"])


@pytest.mark.no_parallel
def test_generate_tenant_token_default_key(client, default_search_key):
    search_rules = {"test": "value"}
    expected = {"searchRules": search_rules, "apiKeyUid": default_search_key.uid}
    token = client.generate_tenant_token(search_rules, api_key=default_search_key)
    assert expected == jwt.decode(jwt=token, key=default_search_key.key, algorithms=["HS256"])


@pytest.mark.no_parallel
def test_generate_tenant_token_default_key_expires(client, default_search_key):
    search_rules: JsonDict = {"test": "value"}
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=1)
    expected: JsonDict = {"searchRules": search_rules}
    expected["apiKeyUid"] = default_search_key.uid
    expected["exp"] = int(datetime.timestamp(expires_at))
    token = client.generate_tenant_token(
        search_rules, api_key=default_search_key, expires_at=expires_at
    )
    assert expected == jwt.decode(jwt=token, key=default_search_key.key, algorithms=["HS256"])


@pytest.mark.no_parallel
def test_generate_tenant_token_default_key_expires_past(client, default_search_key):
    search_rules: JsonDict = {"test": "value"}
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=-1)
    with pytest.raises(ValueError):
        client.generate_tenant_token(
            search_rules, api_key=default_search_key, expires_at=expires_at
        )


@pytest.mark.no_parallel
def test_generate_tenant_token_invalid_restriction(test_key_info, client):
    test_key_info.indexes = ["good"]
    key = client.create_key(test_key_info)
    payload = {"indexes": ["bad"]}

    with pytest.raises(InvalidRestriction):
        client.generate_tenant_token(payload, api_key=key)


@pytest.mark.no_parallel
def test_get_indexes(client, indexes_sample):
    _, index_uid, index_uid2 = indexes_sample
    response = client.get_indexes()
    response_uids = [x.uid for x in response]

    assert index_uid in response_uids
    assert index_uid2 in response_uids
    assert len(response) == 2


@pytest.mark.usefixtures("indexes_sample")
def test_get_indexes_offset_and_limit(client):
    response = client.get_indexes(offset=1, limit=1)
    assert len(response) == 1


@pytest.mark.usefixtures("indexes_sample")
@pytest.mark.no_parallel
def test_get_indexes_offset(client):
    response = client.get_indexes(offset=1)
    assert len(response) >= 1 and len(response) <= 20


@pytest.mark.usefixtures("indexes_sample")
def test_get_indexes_limit(client):
    response = client.get_indexes(limit=1)
    assert len(response) == 1


@pytest.mark.no_parallel
def test_get_indexes_none(client):
    response = client.get_indexes()

    assert response is None


@pytest.mark.usefixtures("indexes_sample")
@pytest.mark.no_parallel
def test_get_index(client, indexes_sample):
    _, index_uid, _ = indexes_sample
    response = client.get_index(index_uid)

    assert response.uid == index_uid
    assert response.primary_key is None
    assert isinstance(response.created_at, datetime)
    assert isinstance(response.updated_at, datetime)


def test_get_index_not_found(client):
    with pytest.raises(MeilisearchApiError):
        client.get_index("test")


def test_index(client):
    uid = str(uuid4())
    response = client.index(uid)

    assert response.uid == uid


def test_get_or_create_index_with_primary_key(client):
    primary_key = "pk_test"
    uid = "test1"
    response = client.get_or_create_index(uid, primary_key)

    assert response.uid == uid
    assert response.primary_key == primary_key


def test_get_or_create_index_no_primary_key(client):
    uid = str(uuid4())
    response = client.get_or_create_index(uid)

    assert response.uid == uid
    assert response.primary_key is None


def test_get_or_create_index_communication_error(client, monkeypatch):
    def mock_get_response(*args, **kwargs):
        raise ConnectError("test", request=Request("GET", url="https://localhost"))

    def mock_post_response(*args, **kwargs):
        raise ConnectError("test", request=Request("POST", url="https://localhost"))

    monkeypatch.setattr(HttpxClient, "get", mock_get_response)
    monkeypatch.setattr(HttpxClient, "post", mock_post_response)
    with pytest.raises(MeilisearchCommunicationError):
        client.get_or_create_index("test")


def test_get_or_create_index_api_error(client, monkeypatch):
    def mock_response(*args, **kwargs):
        raise MeilisearchApiError("test", Response(status_code=404))

    monkeypatch.setattr(Client, "get_index", mock_response)
    with pytest.raises(MeilisearchApiError):
        client.get_or_create_index("test")


@pytest.mark.no_parallel
def test_get_all_stats(client, indexes_sample):
    _, index_uid, index_uid2 = indexes_sample
    response = client.get_all_stats()

    assert index_uid in response.indexes
    assert index_uid2 in response.indexes


@pytest.mark.usefixtures("indexes_sample")
@pytest.mark.no_parallel
def test_get_raw_index(client, indexes_sample):
    _, index_uid, _ = indexes_sample
    response = client.get_raw_index(index_uid)

    assert response.uid == index_uid
    assert isinstance(response, IndexInfo)


def test_get_raw_index_none(client):
    response = client.get_raw_index("test")

    assert response is None


@pytest.mark.no_parallel
def test_get_raw_indexes(client, indexes_sample):
    _, index_uid, index_uid2 = indexes_sample
    response = client.get_raw_indexes()
    response_uids = [x.uid for x in response]

    assert index_uid in response_uids
    assert index_uid2 in response_uids
    assert len(response) == 2


@pytest.mark.usefixtures("indexes_sample")
def test_get_raw_indexes_offset_and_limit(client):
    response = client.get_raw_indexes(offset=1, limit=1)
    assert len(response) == 1


@pytest.mark.usefixtures("indexes_sample")
def test_get_raw_indexes_offset(client):
    response = client.get_raw_indexes(offset=1)
    assert len(response) >= 1 and len(response) <= 20


@pytest.mark.usefixtures("indexes_sample")
def test_get_raw_indexes_limit(client):
    response = client.get_raw_indexes(limit=1)
    assert len(response) == 1


@pytest.mark.no_parallel
def test_get_raw_indexes_none(client):
    response = client.get_raw_indexes()

    assert response is None


def test_health(client):
    health = client.health()

    assert health.status == "available"


def test_create_key(test_key_info, client):
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=2)
    test_key_info.expires_at = expires_at
    key = client.create_key(test_key_info)

    assert key.description == test_key_info.description
    assert key.actions == test_key_info.actions
    assert key.indexes == test_key_info.indexes
    assert key.expires_at == expires_at.replace(tzinfo=None)


def test_create_key_no_expires(test_key_info, client):
    key = client.create_key(test_key_info)

    assert key.description == test_key_info.description
    assert key.actions == test_key_info.actions
    assert key.indexes == test_key_info.indexes
    assert key.expires_at is None


def test_delete_key(test_key, client):
    result = client.delete_key(test_key.key)
    assert result == 204

    with pytest.raises(MeilisearchApiError):
        client.get_key(test_key.key)


@pytest.mark.no_parallel
def test_get_keys(client):
    response = client.get_keys()
    assert len(response.results) >= 3


def test_get_keys_offset_and_limit(client):
    response = client.get_keys(offset=1, limit=1)
    assert len(response.results) == 1


@pytest.mark.no_parallel
def test_get_keys_offset(client):
    response = client.get_keys(offset=1)
    assert len(response.results) >= 1 and len(response.results) <= 20


def test_get_keys_limit(client):
    response = client.get_keys(limit=1)
    assert len(response.results) == 1


@pytest.mark.no_parallel
def test_get_key(test_key, client):
    key = client.get_key(test_key.key)
    assert key.description == test_key.description


@pytest.mark.no_parallel
def test_update_key(test_key, client):
    update_key_info = KeyUpdate(
        key=test_key.key,
        description="updated",
    )

    key = client.update_key(update_key_info)

    assert key.description == update_key_info.description
    assert key.actions == test_key.actions
    assert key.indexes == test_key.indexes
    assert key.expires_at == test_key.expires_at


def test_get_version(client):
    response = client.get_version()

    assert isinstance(response, Version)


@pytest.mark.no_parallel
def test_create_dump(client, index_with_documents):
    index_with_documents()
    response = client.create_dump()
    client.wait_for_task(response.task_uid)

    dump_status = client.get_task(response.task_uid)
    assert dump_status.status == "succeeded"
    assert dump_status.task_type == "dumpCreation"


@pytest.mark.no_parallel
def test_create_snapshot(client, index_with_documents):
    index_with_documents()
    response = client.create_snapshot()
    client.wait_for_task(response.task_uid)

    snapshot_status = client.get_task(response.task_uid)
    assert snapshot_status.status == "succeeded"
    assert snapshot_status.task_type == "snapshotCreation"


def test_no_master_key(base_url, ssl_verify):
    with pytest.raises(MeilisearchApiError):
        client = Client(base_url, verify=ssl_verify)
        client.create_index("some_index")


def test_bad_master_key(base_url, master_key, ssl_verify):
    with pytest.raises(MeilisearchApiError):
        client = Client(base_url, verify=ssl_verify)
        client.create_index("some_index", f"{master_key}bad")


def test_communication_error(master_key, ssl_verify):
    with pytest.raises(MeilisearchCommunicationError):
        client = Client("https://wrongurl:1234", master_key, timeout=1, verify=ssl_verify)
        client.create_index("some_index")


def test_remote_protocol_error(client, monkeypatch):
    def mock_error(*args, **kwargs):
        raise RemoteProtocolError("error", request=args[0])

    monkeypatch.setattr(HttpxClient, "post", mock_error)
    with pytest.raises(MeilisearchCommunicationError):
        client.create_index("some_index")


def test_connection_timeout(client, monkeypatch):
    def mock_error(*args, **kwargs):
        raise ConnectTimeout("error")

    monkeypatch.setattr(HttpxClient, "post", mock_error)
    with pytest.raises(MeilisearchCommunicationError):
        client.create_index("some_index")


@pytest.mark.no_parallel
def test_swap_indexes(client, empty_index):
    index_a = empty_index()
    index_b = empty_index()
    task_a = index_a.add_documents([{"id": 1, "title": index_a.uid}])
    task_b = index_b.add_documents([{"id": 1, "title": index_b.uid}])
    client.wait_for_task(task_a.task_uid)
    client.wait_for_task(task_b.task_uid)
    swapTask = client.swap_indexes([(index_a.uid, index_b.uid)])
    task = client.wait_for_task(swapTask.task_uid)
    doc_a = client.index(index_a.uid).get_document(1)
    doc_b = client.index(index_b.uid).get_document(1)

    assert doc_a["title"] == index_b.uid
    assert doc_b["title"] == index_a.uid
    assert task.task_type == "indexSwap"


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
def test_cancel_statuses(client):
    task = client.cancel_tasks(statuses=["enqueued", "processing"])
    client.wait_for_task(task.task_uid)
    completed_task = client.get_task(task.task_uid)
    tasks = client.get_tasks(types="taskCancelation")

    assert completed_task.index_uid is None
    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert "statuses=enqueued%2Cprocessing" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
def test_cancel_tasks_uids(client):
    task = client.cancel_tasks(uids=["1", "2"])
    client.wait_for_task(task.task_uid)
    completed_task = client.get_task(task.task_uid)
    tasks = client.get_tasks(types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert "uids=1%2C2" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
def test_cancel_tasks_index_uids(client):
    task = client.cancel_tasks(index_uids=["1"])

    client.wait_for_task(task.task_uid)
    completed_task = client.get_task(task.task_uid)
    tasks = client.get_tasks(types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert "indexUids=1" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
def test_cancel_tasks_types(client):
    task = client.cancel_tasks(types=["taskDeletion"])
    client.wait_for_task(task.task_uid)
    completed_task = client.get_task(task.task_uid)
    tasks = client.get_tasks(types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert "types=taskDeletion" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
def test_cancel_tasks_before_enqueued_at(client):
    before = datetime.now()
    task = client.cancel_tasks(before_enqueued_at=before)
    client.wait_for_task(task.task_uid)
    completed_task = client.get_task(task.task_uid)
    tasks = client.get_tasks(types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert (
        f"beforeEnqueuedAt={quote_plus(before.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
def test_cancel_tasks_after_enqueued_at(client):
    after = datetime.now()
    task = client.cancel_tasks(after_enqueued_at=after)
    client.wait_for_task(task.task_uid)
    completed_task = client.get_task(task.task_uid)
    tasks = client.get_tasks(types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert (
        f"afterEnqueuedAt={quote_plus(after.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
def test_cancel_tasks_before_started_at(client):
    before = datetime.now()
    task = client.cancel_tasks(before_started_at=before)
    client.wait_for_task(task.task_uid)
    completed_task = client.get_task(task.task_uid)
    tasks = client.get_tasks(types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert (
        f"beforeStartedAt={quote_plus(before.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
def test_cancel_tasks_after_finished_at(client):
    after = datetime.now()
    task = client.cancel_tasks(after_finished_at=after)
    client.wait_for_task(task.task_uid)
    completed_task = client.get_task(task.task_uid)
    tasks = client.get_tasks(types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert (
        f"afterFinishedAt={quote_plus(after.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
def test_cancel_task_no_params(client):
    task = client.cancel_tasks()
    client.wait_for_task(task.task_uid)
    completed_task = client.get_task(task.task_uid)
    tasks = client.get_tasks(types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert "statuses=enqueued%2Cprocessing" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
def test_delete_statuses(client):
    task = client.delete_tasks(statuses=["enqueued", "processing"])
    client.wait_for_task(task.task_uid)
    deleted_tasks = client.get_task(task.task_uid)
    tasks = client.get_tasks(types="taskDeletion")

    assert deleted_tasks.status == "succeeded"
    assert deleted_tasks.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert "statuses=enqueued%2Cprocessing" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
def test_delete_tasks(client):
    task = client.delete_tasks(uids=["1", "2"])
    client.wait_for_task(task.task_uid)
    completed_task = client.get_task(task.task_uid)
    tasks = client.get_tasks(types="taskDeletion")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert "uids=1%2C2" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
def test_delete_tasks_index_uids(client):
    task = client.delete_tasks(index_uids=["1"])
    client.wait_for_task(task.task_uid)
    deleted_task = client.get_task(task.task_uid)
    tasks = client.get_tasks(types="taskDeletion")

    assert deleted_task.status == "succeeded"
    assert deleted_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert "indexUids=1" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
def test_delete_tasks_types(client):
    task = client.delete_tasks(types=["taskDeletion"])
    client.wait_for_task(task.task_uid)
    deleted_task = client.get_task(task.task_uid)
    tasks = client.get_tasks(types="taskDeletion")

    assert deleted_task.status == "succeeded"
    assert deleted_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert "types=taskDeletion" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
def test_delete_tasks_before_enqueued_at(client):
    before = datetime.now()
    task = client.delete_tasks(before_enqueued_at=before)
    client.wait_for_task(task.task_uid)
    deleted_task = client.get_task(task.task_uid)
    tasks = client.get_tasks(types="taskDeletion")

    assert deleted_task.status == "succeeded"
    assert deleted_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert (
        f"beforeEnqueuedAt={quote_plus(before.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
def test_delete_tasks_after_enqueued_at(client):
    after = datetime.now()
    task = client.delete_tasks(after_enqueued_at=after)
    client.wait_for_task(task.task_uid)
    deleted_task = client.get_task(task.task_uid)
    tasks = client.get_tasks(types="taskDeletion")

    assert deleted_task.status == "succeeded"
    assert deleted_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert (
        f"afterEnqueuedAt={quote_plus(after.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
def test_delete_tasks_before_started_at(client):
    before = datetime.now()
    task = client.delete_tasks(before_started_at=before)
    client.wait_for_task(task.task_uid)
    deleted_task = client.get_task(task.task_uid)
    tasks = client.get_tasks(types="taskDeletion")

    assert deleted_task.status == "succeeded"
    assert deleted_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert (
        f"beforeStartedAt={quote_plus(before.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
def test_delete_tasks_after_finished_at(client):
    after = datetime.now()
    task = client.delete_tasks(after_finished_at=after)
    client.wait_for_task(task.task_uid)
    deleted_task = client.get_task(task.task_uid)
    tasks = client.get_tasks(types="taskDeletion")

    assert deleted_task.status == "succeeded"
    assert deleted_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert (
        f"afterFinishedAt={quote_plus(after.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
def test_delete_tasks_no_params(client):
    task = client.delete_tasks()
    client.wait_for_task(task.task_uid)
    deleted_tasks = client.get_task(task.task_uid)
    tasks = client.get_tasks(types="taskDeletion")

    assert deleted_tasks.status == "succeeded"
    assert deleted_tasks.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert (
        "statuses=canceled%2Cenqueued%2Cfailed%2Cprocessing%2Csucceeded"
        in tasks.results[0].details["originalFilter"]
    )


def test_get_tasks(client, empty_index, small_movies):
    index = empty_index()
    tasks = client.get_tasks()
    current_tasks = len(tasks.results)
    response = index.add_documents(small_movies)
    client.wait_for_task(response.task_uid)
    response = index.add_documents(small_movies)
    client.wait_for_task(response.task_uid)
    response = client.get_tasks()
    assert len(response.results) >= current_tasks


def test_get_tasks_for_index(client, empty_index, small_movies):
    index = empty_index()
    tasks = client.get_tasks(index_ids=[index.uid])
    current_tasks = len(tasks.results)
    response = index.add_documents(small_movies)
    client.wait_for_task(response.task_uid)
    response = index.add_documents(small_movies)
    client.wait_for_task(response.task_uid)
    response = client.get_tasks(index_ids=[index.uid])
    assert len(response.results) >= current_tasks
    uid = set([x.index_uid for x in response.results])
    assert len(uid) == 1
    assert next(iter(uid)) == index.uid


@pytest.mark.no_parallel
def test_get_tasks_reverse(client, empty_index, small_movies):
    index = empty_index()
    tasks = client.get_tasks()
    current_tasks = len(tasks.results)
    response = index.add_documents(small_movies)
    client.wait_for_task(response.task_uid)
    response = index.add_documents(small_movies)
    client.wait_for_task(response.task_uid)
    response = client.get_tasks(reverse=True)
    assert len(response.results) >= current_tasks


def test_get_tasks_for_index_reverse(client, empty_index, small_movies):
    index = empty_index()
    tasks = client.get_tasks(index_ids=[index.uid])
    current_tasks = len(tasks.results)
    response = index.add_documents(small_movies)
    client.wait_for_task(response.task_uid)
    response = index.add_documents(small_movies)
    client.wait_for_task(response.task_uid)
    response = client.get_tasks(index_ids=[index.uid], reverse=True)
    assert len(response.results) >= current_tasks
    uid = set([x.index_uid for x in response.results])
    assert len(uid) == 1
    assert next(iter(uid)) == index.uid


def test_get_task(client, empty_index, small_movies):
    index = empty_index()
    response = index.add_documents(small_movies)
    client.wait_for_task(response.task_uid)
    update = client.get_task(response.task_uid)
    assert update.status == "succeeded"


def test_wait_for_task(client, empty_index, small_movies):
    index = empty_index()
    response = index.add_documents(small_movies)
    update = client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"


def test_wait_for_task_no_timeout(client, empty_index, small_movies):
    index = empty_index()
    response = index.add_documents(small_movies)
    update = client.wait_for_task(response.task_uid, timeout_in_ms=None)
    assert update.status == "succeeded"


def test_wait_for_pending_update_time_out(client, empty_index, small_movies):
    index = empty_index()
    with pytest.raises(MeilisearchTimeoutError):
        response = index.add_documents(small_movies)
        client.wait_for_task(response.task_uid, timeout_in_ms=1, interval_in_ms=1)

    client.wait_for_task(  # Make sure the indexing finishes so subsequent tests don't have issues.
        response.task_uid
    )


def test_wait_for_task_raise_for_status_true(client, empty_index, small_movies):
    index = empty_index()
    response = index.add_documents(small_movies)
    update = client.wait_for_task(response.task_uid, raise_for_status=True)
    assert update.status == "succeeded"


def test_wait_for_task_raise_for_status_true_no_timeout(
    client, empty_index, small_movies, base_url, monkeypatch
):
    def mock_get_response(*args, **kwargs):
        task = {
            "uid": args[1].split("/")[1],
            "index_uid": "7defe207-8165-4b69-8170-471456e295e0",
            "status": "failed",
            "task_type": "indexDeletion",
            "details": {"deletedDocuments": 30},
            "error": None,
            "canceled_by": None,
            "duration": "PT0.002765250S",
            "enqueued_at": "2023-06-09T01:03:48.311936656Z",
            "started_at": "2023-06-09T01:03:48.314143377Z",
            "finished_at": "2023-06-09T01:03:48.316536088Z",
        }

        return Response(200, json=task, request=Request("get", url=f"{base_url}/{args[1]}"))

    index = empty_index()
    response = index.add_documents(small_movies)
    monkeypatch.setattr(HttpxClient, "get", mock_get_response)
    with pytest.raises(MeilisearchTaskFailedError):
        client.wait_for_task(response.task_uid, raise_for_status=True, timeout_in_ms=None)


def test_wait_for_task_raise_for_status_false(
    client, empty_index, small_movies, base_url, monkeypatch
):
    def mock_get_response(*args, **kwargs):
        task = {
            "uid": args[1].split("/")[1],
            "index_uid": "7defe207-8165-4b69-8170-471456e295e0",
            "status": "failed",
            "task_type": "indexDeletion",
            "details": {"deletedDocuments": 30},
            "error": None,
            "canceled_by": None,
            "duration": "PT0.002765250S",
            "enqueued_at": "2023-06-09T01:03:48.311936656Z",
            "started_at": "2023-06-09T01:03:48.314143377Z",
            "finished_at": "2023-06-09T01:03:48.316536088Z",
        }
        return Response(200, json=task, request=Request("get", url=f"{base_url}/{args[1]}"))

    index = empty_index()
    response = index.add_documents(small_movies)
    monkeypatch.setattr(HttpxClient, "get", mock_get_response)
    with pytest.raises(MeilisearchTaskFailedError):
        client.wait_for_task(response.task_uid, raise_for_status=True)


@pytest.mark.parametrize("http2, expected", [(True, "HTTP/2"), (False, "HTTP/1.1")])
def test_http_version(http2, expected, master_key, ssl_verify, base_url, http2_enabled):
    if not http2_enabled:
        pytest.skip("HTTP/2 is not enabled")
    client = Client(base_url, master_key, http2=http2, verify=ssl_verify)
    assert client.http_client.get("health").http_version == expected


def test_get_batches(client, empty_index, small_movies):
    # Add documents to create batches
    index = empty_index()
    tasks = index.add_documents_in_batches(small_movies, batch_size=5)
    for task in tasks:
        client.wait_for_task(task.task_uid)

    result = client.get_batches()
    assert len(result.results) > 0


def test_get_batches_with_params(client, empty_index, small_movies):
    # Add documents to create batches
    index = empty_index()
    tasks = index.add_documents_in_batches(small_movies, batch_size=5)
    for task in tasks:
        client.wait_for_task(task.task_uid)

    result = client.get_batches(uids=[task.task_uid for task in tasks])
    assert len(result.results) > 0


def test_get_batch(client, empty_index, small_movies):
    # Add documents to create batches
    index = empty_index()
    tasks = index.add_documents_in_batches(small_movies, batch_size=5)
    for task in tasks:
        client.wait_for_task(task.task_uid)

    task = client.get_task(tasks[0].task_uid)
    result = client.get_batch(task.batch_uid)

    assert result.uid == task.batch_uid


def test_get_batch_not_found(client):
    with pytest.raises(BatchNotFoundError):
        client.get_batch(999999999)


def test_get_networks(client):
    response = client.get_networks()

    assert isinstance(response, Network)


def test_add_or_update_networks(client):
    network = Network(
        self_="remote_1",
        remotes={
            "remote_1": {"url": "http://localhost:7700", "searchApiKey": "xxxxxxxxxxxxxx"},
            "remote_2": {"url": "http://localhost:7720", "searchApiKey": "xxxxxxxxxxxxxxx"},
        },
    )
    response = client.add_or_update_networks(network=network)

    assert response.self_ == "remote_1"
    assert len(response.remotes) >= 2
    assert "remote_1" in response.remotes
    assert "remote_2" in response.remotes
