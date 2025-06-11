from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus
from uuid import uuid4

import jwt
import pytest
from httpx import AsyncClient as HttpxAsyncClient
from httpx import ConnectError, ConnectTimeout, RemoteProtocolError, Request, Response

from meilisearch_python_sdk import AsyncClient
from meilisearch_python_sdk._task import (
    async_get_task,
)
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
async def test_key(async_client):
    key_info = KeyCreate(description="test", actions=["search"], indexes=["movies"])
    key = await async_client.create_key(key_info)

    yield key

    try:
        await async_client.delete_key(key.key)
    except MeilisearchApiError:
        pass


@pytest.fixture
async def test_key_info(async_client):
    key_info = KeyCreate(description="test", actions=["search"], indexes=["movies"])

    yield key_info

    try:
        keys = await async_client.get_keys()
        key = next(x for x in keys.results if x.description == key_info.description)
        await async_client.delete_key(key.key)
    except MeilisearchApiError:
        pass


async def wait_for_dump_creation(
    async_client, dump_uid, timeout_in_ms=10000.0, interval_in_ms=500.0
):
    start_time = datetime.now()
    elapsed_time = 0.0
    while elapsed_time < timeout_in_ms:
        dump = await async_client.get_dump_status(dump_uid)
        if dump.status != "in_progress":
            return None
        await asyncio.sleep(interval_in_ms / 1000)
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
async def test_headers(api_key, custom_headers, expected, ssl_verify):
    async with AsyncClient(
        "https://127.0.0.1:7700", api_key=api_key, custom_headers=custom_headers, verify=ssl_verify
    ) as client:
        assert client._headers == expected


async def test_create_index_with_primary_key(async_client):
    uid = str(uuid4())
    primary_key = "pk_test"
    index = await async_client.create_index(uid=uid, primary_key=primary_key)

    assert index.uid == uid

    assert index.primary_key == primary_key
    assert isinstance(index.created_at, datetime)
    assert isinstance(index.updated_at, datetime)


async def test_create_index_no_primary_key(async_client):
    uid = str(uuid4())
    index = await async_client.create_index(uid=uid)

    assert index.uid == uid

    assert index.primary_key is None
    assert isinstance(index.created_at, datetime)
    assert isinstance(index.updated_at, datetime)


async def test_create_index_orjson_handler(async_client_orjson_handler):
    uid = str(uuid4())
    index = await async_client_orjson_handler.create_index(uid=uid)

    assert index.uid == uid

    assert index.primary_key is None
    assert isinstance(index.created_at, datetime)
    assert isinstance(index.updated_at, datetime)


async def test_create_index_ujson_handler(async_client_ujson_handler):
    uid = str(uuid4())
    index = await async_client_ujson_handler.create_index(uid=uid)

    assert index.uid == uid

    assert index.primary_key is None
    assert isinstance(index.created_at, datetime)
    assert isinstance(index.updated_at, datetime)


async def test_create_index_with_settings(async_client, new_settings):
    uid = str(uuid4())
    index = await async_client.create_index(uid=uid, settings=new_settings)
    assert index.uid == uid
    response = await index.get_settings()
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
    assert response.search_cutoff_ms == new_settings.search_cutoff_ms
    assert response.dictionary == new_settings.dictionary


async def test_create_index_with_settings_no_wait(async_client, new_settings):
    uid = str(uuid4())
    index = await async_client.create_index(uid=uid, settings=new_settings, wait=False)
    assert index.uid == uid


@pytest.mark.no_parallel
async def test_create_keys_with_wildcarded_actions(async_client, test_key_info):
    test_key_info.actions = ["documents.*"]
    key = await async_client.create_key(test_key_info)

    assert key.actions == ["documents.*"]


@pytest.mark.no_parallel
async def test_generate_tenant_token_custom_key(async_client, test_key):
    search_rules = {"test": "value"}
    expected = {"searchRules": search_rules, "apiKeyUid": test_key.uid}
    token = async_client.generate_tenant_token(search_rules, api_key=test_key)
    assert expected == jwt.decode(jwt=token, key=test_key.key, algorithms=["HS256"])


@pytest.mark.no_parallel
async def test_generate_tenant_token_default_key(async_client, default_search_key):
    search_rules = {"test": "value"}
    expected = {"searchRules": search_rules, "apiKeyUid": default_search_key.uid}
    token = async_client.generate_tenant_token(search_rules, api_key=default_search_key)
    assert expected == jwt.decode(jwt=token, key=default_search_key.key, algorithms=["HS256"])


@pytest.mark.no_parallel
async def test_generate_tenant_token_default_key_expires(async_client, default_search_key):
    search_rules: JsonDict = {"test": "value"}
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=1)
    expected: JsonDict = {"searchRules": search_rules}
    expected["apiKeyUid"] = default_search_key.uid
    expected["exp"] = int(datetime.timestamp(expires_at))
    token = async_client.generate_tenant_token(
        search_rules, api_key=default_search_key, expires_at=expires_at
    )
    assert expected == jwt.decode(jwt=token, key=default_search_key.key, algorithms=["HS256"])


@pytest.mark.no_parallel
async def test_generate_tenant_token_default_key_expires_past(async_client, default_search_key):
    search_rules: JsonDict = {"test": "value"}
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=-1)
    with pytest.raises(ValueError):
        async_client.generate_tenant_token(
            search_rules, api_key=default_search_key, expires_at=expires_at
        )


@pytest.mark.no_parallel
async def test_generate_tenant_token_invalid_restriction(test_key_info, async_client):
    test_key_info.indexes = ["good"]
    key = await async_client.create_key(test_key_info)
    payload = {"indexes": ["bad"]}

    with pytest.raises(InvalidRestriction):
        async_client.generate_tenant_token(payload, api_key=key)


@pytest.mark.no_parallel
async def test_get_indexes(async_client, async_indexes_sample):
    _, index_uid, index_uid2 = async_indexes_sample
    response = await async_client.get_indexes()
    response_uids = [x.uid for x in response]

    assert index_uid in response_uids
    assert index_uid2 in response_uids
    assert len(response) == 2


@pytest.mark.usefixtures("async_indexes_sample")
async def test_get_indexes_offset_and_limit(async_client):
    response = await async_client.get_indexes(offset=1, limit=1)
    assert len(response) == 1


@pytest.mark.usefixtures("async_indexes_sample")
@pytest.mark.no_parallel
async def test_get_indexes_offset(async_client):
    response = await async_client.get_indexes(offset=1)
    assert len(response) >= 1 and len(response) <= 20


@pytest.mark.usefixtures("async_indexes_sample")
async def test_get_indexes_limit(async_client):
    response = await async_client.get_indexes(limit=1)
    assert len(response) == 1


@pytest.mark.no_parallel
async def test_get_indexes_none(async_client):
    response = await async_client.get_indexes()

    assert response is None


@pytest.mark.no_parallel
async def test_get_index(async_client, async_indexes_sample):
    _, index_uid, _ = async_indexes_sample
    response = await async_client.get_index(index_uid)

    assert response.uid == index_uid
    assert response.primary_key is None
    assert isinstance(response.created_at, datetime)
    assert isinstance(response.updated_at, datetime)


async def test_get_index_not_found(async_client):
    with pytest.raises(MeilisearchApiError):
        await async_client.get_index("test")


def test_index(async_client):
    uid = str(uuid4())
    response = async_client.index(uid)

    assert response.uid == uid


async def test_get_or_create_index_with_primary_key(async_client):
    primary_key = "pk_test"
    uid = "test1"
    response = await async_client.get_or_create_index(uid, primary_key)

    assert response.uid == uid
    assert response.primary_key == primary_key


async def test_get_or_create_index_no_primary_key(async_client):
    uid = str(uuid4())
    response = await async_client.get_or_create_index(uid)

    assert response.uid == uid
    assert response.primary_key is None


async def test_get_or_create_index_communication_error(async_client, monkeypatch):
    async def mock_get_response(*args, **kwargs):
        raise ConnectError("test", request=Request("GET", url="https://localhost"))

    async def mock_post_response(*args, **kwargs):
        raise ConnectError("test", request=Request("POST", url="https://localhost"))

    monkeypatch.setattr(HttpxAsyncClient, "get", mock_get_response)
    monkeypatch.setattr(HttpxAsyncClient, "post", mock_post_response)
    with pytest.raises(MeilisearchCommunicationError):
        await async_client.get_or_create_index("test")


async def test_get_or_create_index_api_error(async_client, monkeypatch):
    async def mock_response(*args, **kwargs):
        raise MeilisearchApiError("test", Response(status_code=404))

    monkeypatch.setattr(AsyncClient, "get_index", mock_response)
    with pytest.raises(MeilisearchApiError):
        await async_client.get_or_create_index("test")


async def test_get_all_stats(async_client, async_indexes_sample):
    _, index_uid, index_uid2 = async_indexes_sample
    response = await async_client.get_all_stats()

    assert index_uid in response.indexes
    assert index_uid2 in response.indexes


async def test_get_raw_index(async_client, async_indexes_sample):
    _, index_uid, _ = async_indexes_sample
    response = await async_client.get_raw_index(index_uid)

    assert response.uid == index_uid
    assert isinstance(response, IndexInfo)


async def test_get_raw_index_none(async_client):
    response = await async_client.get_raw_index("test")

    assert response is None


@pytest.mark.no_parallel
async def test_get_raw_indexes(async_client, async_indexes_sample):
    _, index_uid, index_uid2 = async_indexes_sample
    response = await async_client.get_raw_indexes()
    response_uids = [x.uid for x in response]

    assert index_uid in response_uids
    assert index_uid2 in response_uids
    assert len(response) == 2


@pytest.mark.usefixtures("async_indexes_sample")
async def test_get_raw_indexes_offset_and_limit(async_client, async_indexes_sample):
    response = await async_client.get_raw_indexes(offset=1, limit=1)
    assert len(response) == 1


@pytest.mark.usefixtures("async_indexes_sample")
async def test_get_raw_indexes_offset(async_client):
    response = await async_client.get_raw_indexes(offset=1)
    assert len(response) >= 1 and len(response) <= 20


@pytest.mark.usefixtures("async_indexes_sample")
async def test_get_raw_indexes_limit(async_client):
    response = await async_client.get_raw_indexes(limit=1)
    assert len(response) == 1


@pytest.mark.no_parallel
async def test_get_raw_indexes_none(async_client):
    response = await async_client.get_raw_indexes()

    assert response is None


async def test_health(async_client):
    health = await async_client.health()

    assert health.status == "available"


async def test_create_key(test_key_info, async_client):
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=2)
    test_key_info.expires_at = expires_at
    key = await async_client.create_key(test_key_info)

    assert key.description == test_key_info.description
    assert key.actions == test_key_info.actions
    assert key.indexes == test_key_info.indexes
    assert key.expires_at == expires_at.replace(tzinfo=None)


async def test_create_key_no_expires(test_key_info, async_client):
    key = await async_client.create_key(test_key_info)

    assert key.description == test_key_info.description
    assert key.actions == test_key_info.actions
    assert key.indexes == test_key_info.indexes
    assert key.expires_at is None


async def test_delete_key(test_key, async_client):
    result = await async_client.delete_key(test_key.key)
    assert result == 204

    with pytest.raises(MeilisearchApiError):
        await async_client.get_key(test_key.key)


@pytest.mark.no_parallel
async def test_get_keys(async_client):
    response = await async_client.get_keys()
    assert len(response.results) >= 3


@pytest.mark.no_parallel
async def test_get_keys_offset_and_limit(async_client):
    response = await async_client.get_keys(offset=1, limit=1)
    assert len(response.results) == 1


@pytest.mark.no_parallel
async def test_get_keys_offset(async_client):
    response = await async_client.get_keys(offset=1)
    assert len(response.results) >= 1 and len(response.results) <= 20


@pytest.mark.no_parallel
async def test_get_keys_limit(async_client):
    response = await async_client.get_keys(limit=1)
    assert len(response.results) == 1


@pytest.mark.no_parallel
async def test_get_key(test_key, async_client):
    key = await async_client.get_key(test_key.key)
    assert key.description == test_key.description


@pytest.mark.no_parallel
async def test_update_key(test_key, async_client):
    update_key_info = KeyUpdate(
        key=test_key.key,
        description="updated",
    )

    key = await async_client.update_key(update_key_info)

    assert key.description == update_key_info.description
    assert key.actions == test_key.actions
    assert key.indexes == test_key.indexes
    assert key.expires_at == test_key.expires_at


async def test_get_version(async_client):
    response = await async_client.get_version()

    assert isinstance(response, Version)


@pytest.mark.no_parallel
async def test_create_dump(async_client, async_index_with_documents):
    index = await async_index_with_documents()
    response = await async_client.create_dump()
    await async_client.wait_for_task(response.task_uid)

    dump_status = await async_get_task(index.http_client, response.task_uid)
    assert dump_status.status == "succeeded"
    assert dump_status.task_type == "dumpCreation"


@pytest.mark.no_parallel
async def test_create_snapshot(async_client, async_index_with_documents):
    index = await async_index_with_documents()
    response = await async_client.create_snapshot()
    await async_client.wait_for_task(response.task_uid)

    snapshot_status = await async_get_task(index.http_client, response.task_uid)
    assert snapshot_status.status == "succeeded"
    assert snapshot_status.task_type == "snapshotCreation"


async def test_no_master_key(base_url, ssl_verify):
    with pytest.raises(MeilisearchApiError):
        async with AsyncClient(base_url, verify=ssl_verify) as client:
            await client.create_index("some_index")


async def test_bad_master_key(base_url, master_key, ssl_verify):
    with pytest.raises(MeilisearchApiError):
        async with AsyncClient(base_url, verify=ssl_verify) as client:
            await client.create_index("some_index", f"{master_key}bad")


async def test_communication_error(master_key):
    with pytest.raises(MeilisearchCommunicationError):
        async with AsyncClient("https://wrongurl:1234", master_key, timeout=1) as client:
            await client.create_index("some_index")


async def test_remote_protocol_error(async_client, monkeypatch):
    def mock_error(*args, **kwargs):
        raise RemoteProtocolError("error", request=args[0])

    monkeypatch.setattr(HttpxAsyncClient, "post", mock_error)
    with pytest.raises(MeilisearchCommunicationError):
        await async_client.create_index("some_index")


async def test_connection_timeout(async_client, monkeypatch):
    def mock_error(*args, **kwargs):
        raise ConnectTimeout("error")

    monkeypatch.setattr(HttpxAsyncClient, "post", mock_error)
    with pytest.raises(MeilisearchCommunicationError):
        await async_client.create_index("some_index")


@pytest.mark.no_parallel
async def test_swap_indexes(async_client, async_empty_index):
    index_a = await async_empty_index()
    index_b = await async_empty_index()
    task_a = await index_a.add_documents([{"id": 1, "title": index_a.uid}])
    task_b = await index_b.add_documents([{"id": 1, "title": index_b.uid}])
    await async_client.wait_for_task(task_a.task_uid)
    await async_client.wait_for_task(task_b.task_uid)
    swapTask = await async_client.swap_indexes([(index_a.uid, index_b.uid)])
    task = await async_client.wait_for_task(swapTask.task_uid)
    doc_a = await async_client.index(index_a.uid).get_document(1)
    doc_b = await async_client.index(index_b.uid).get_document(1)

    assert doc_a["title"] == index_b.uid
    assert doc_b["title"] == index_a.uid
    assert task.task_type == "indexSwap"


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
async def test_cancel_task_statuses(async_client):
    task = await async_client.cancel_tasks(statuses=["enqueued", "processing"])
    await async_client.wait_for_task(task.task_uid)
    completed_task = await async_client.get_task(task.task_uid)
    tasks = await async_client.get_tasks(types="taskCancelation")

    assert completed_task.index_uid is None
    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert "statuses=enqueued%2Cprocessing" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
async def test_cancel_tasks_uids(async_client):
    task = await async_client.cancel_tasks(uids=["1", "2"])
    await async_client.wait_for_task(task.task_uid)
    completed_task = await async_client.get_task(task.task_uid)
    tasks = await async_client.get_tasks(types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert "uids=1%2C2" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
async def test_cancel_tasks_index_uids(async_client):
    task = await async_client.cancel_tasks(index_uids=["1"])

    await async_client.wait_for_task(task.task_uid)
    completed_task = await async_client.get_task(task.task_uid)
    tasks = await async_client.get_tasks(types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert "indexUids=1" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
async def test_cancel_tasks_types(async_client):
    task = await async_client.cancel_tasks(types=["taskDeletion"])
    await async_client.wait_for_task(task.task_uid)
    completed_task = await async_client.get_task(task.task_uid)
    tasks = await async_client.get_tasks(types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert "types=taskDeletion" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
async def test_cancel_tasks_before_enqueued_at(async_client):
    before = datetime.now()
    task = await async_client.cancel_tasks(before_enqueued_at=before)
    await async_client.wait_for_task(task.task_uid)
    completed_task = await async_client.get_task(task.task_uid)
    tasks = await async_client.get_tasks(types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert (
        f"beforeEnqueuedAt={quote_plus(before.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
async def test_cancel_tasks_after_enqueued_at(async_client):
    after = datetime.now()
    task = await async_client.cancel_tasks(after_enqueued_at=after)
    await async_client.wait_for_task(task.task_uid)
    completed_task = await async_client.get_task(task.task_uid)
    tasks = await async_client.get_tasks(types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert (
        f"afterEnqueuedAt={quote_plus(after.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
async def test_cancel_tasks_before_started_at(async_client):
    before = datetime.now()
    task = await async_client.cancel_tasks(before_started_at=before)
    await async_client.wait_for_task(task.task_uid)
    completed_task = await async_client.get_task(task.task_uid)
    tasks = await async_client.get_tasks(types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert (
        f"beforeStartedAt={quote_plus(before.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
async def test_cancel_tasks_after_finished_at(async_client):
    after = datetime.now()
    task = await async_client.cancel_tasks(after_finished_at=after)
    await async_client.wait_for_task(task.task_uid)
    completed_task = await async_client.get_task(task.task_uid)
    tasks = await async_client.get_tasks(types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert (
        f"afterFinishedAt={quote_plus(after.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
async def test_cancel_task_no_params(async_client):
    task = await async_client.cancel_tasks()
    await async_client.wait_for_task(task.task_uid)
    completed_task = await async_client.get_task(task.task_uid)
    tasks = await async_client.get_tasks(types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert "statuses=enqueued%2Cprocessing" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
async def test_delete_statuses(async_client):
    task = await async_client.delete_tasks(statuses=["enqueued", "processing"])
    await async_client.wait_for_task(task.task_uid)
    deleted_tasks = await async_client.get_task(task.task_uid)
    tasks = await async_client.get_tasks(types="taskDeletion")

    assert deleted_tasks.status == "succeeded"
    assert deleted_tasks.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert "statuses=enqueued%2Cprocessing" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
async def test_delete_tasks(async_client):
    task = await async_client.delete_tasks(uids=["1", "2"])
    await async_client.wait_for_task(task.task_uid)
    completed_task = await async_client.get_task(task.task_uid)
    tasks = await async_client.get_tasks(types="taskDeletion")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert "uids=1%2C2" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
async def test_delete_tasks_index_uids(async_client):
    task = await async_client.delete_tasks(index_uids=["1"])
    await async_client.wait_for_task(task.task_uid)
    deleted_task = await async_client.get_task(task.task_uid)
    tasks = await async_client.get_tasks(types="taskDeletion")

    assert deleted_task.status == "succeeded"
    assert deleted_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert "indexUids=1" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
async def test_delete_tasks_types(async_client):
    task = await async_client.delete_tasks(types=["taskDeletion"])
    await async_client.wait_for_task(task.task_uid)
    deleted_task = await async_client.get_task(task.task_uid)
    tasks = await async_client.get_tasks(types="taskDeletion")

    assert deleted_task.status == "succeeded"
    assert deleted_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert "types=taskDeletion" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
async def test_delete_tasks_before_enqueued_at(async_client):
    before = datetime.now()
    task = await async_client.delete_tasks(before_enqueued_at=before)
    await async_client.wait_for_task(task.task_uid)
    deleted_task = await async_client.get_task(task.task_uid)
    tasks = await async_client.get_tasks(types="taskDeletion")

    assert deleted_task.status == "succeeded"
    assert deleted_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert (
        f"beforeEnqueuedAt={quote_plus(before.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
async def test_delete_tasks_after_enqueued_at(async_client):
    after = datetime.now()
    task = await async_client.delete_tasks(after_enqueued_at=after)
    await async_client.wait_for_task(task.task_uid)
    deleted_task = await async_client.get_task(task.task_uid)
    tasks = await async_client.get_tasks(types="taskDeletion")

    assert deleted_task.status == "succeeded"
    assert deleted_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert (
        f"afterEnqueuedAt={quote_plus(after.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
async def test_delete_tasks_before_started_at(async_client):
    before = datetime.now()
    task = await async_client.delete_tasks(before_started_at=before)
    await async_client.wait_for_task(task.task_uid)
    deleted_task = await async_client.get_task(task.task_uid)
    tasks = await async_client.get_tasks(types="taskDeletion")

    assert deleted_task.status == "succeeded"
    assert deleted_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert (
        f"beforeStartedAt={quote_plus(before.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
async def test_delete_tasks_after_finished_at(async_client):
    after = datetime.now()
    task = await async_client.delete_tasks(after_finished_at=after)
    await async_client.wait_for_task(task.task_uid)
    deleted_task = await async_client.get_task(task.task_uid)
    tasks = await async_client.get_tasks(types="taskDeletion")

    assert deleted_task.status == "succeeded"
    assert deleted_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert (
        f"afterFinishedAt={quote_plus(after.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
@pytest.mark.no_parallel
async def test_delete_no_params(async_client):
    task = await async_client.delete_tasks()
    await async_client.wait_for_task(task.task_uid)
    deleted_tasks = await async_client.get_task(task.task_uid)
    tasks = await async_client.get_tasks(types="taskDeletion")

    assert deleted_tasks.status == "succeeded"
    assert deleted_tasks.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert (
        "statuses=canceled%2Cenqueued%2Cfailed%2Cprocessing%2Csucceeded"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.no_parallel
async def test_get_tasks(async_client, async_empty_index, small_movies):
    index = await async_empty_index()
    tasks = await async_client.get_tasks()
    current_tasks = len(tasks.results)
    response = await index.add_documents(small_movies)
    await async_client.wait_for_task(response.task_uid)
    response = await index.add_documents(small_movies)
    await async_client.wait_for_task(response.task_uid)
    response = await async_client.get_tasks()
    assert len(response.results) >= current_tasks


@pytest.mark.no_parallel
async def test_get_tasks_for_index(async_client, async_empty_index, small_movies):
    index = await async_empty_index()
    tasks = await async_client.get_tasks(index_ids=[index.uid])
    current_tasks = len(tasks.results)
    response = await index.add_documents(small_movies)
    await async_client.wait_for_task(response.task_uid)
    response = await index.add_documents(small_movies)
    await async_client.wait_for_task(response.task_uid)
    response = await async_client.get_tasks(index_ids=[index.uid])
    assert len(response.results) >= current_tasks
    uid = set([x.index_uid for x in response.results])
    assert len(uid) == 1
    assert next(iter(uid)) == index.uid


@pytest.mark.no_parallel
async def test_get_tasks_reverse(async_client, async_empty_index, small_movies):
    index = await async_empty_index()
    tasks = await async_client.get_tasks()
    current_tasks = len(tasks.results)
    response = await index.add_documents(small_movies)
    await async_client.wait_for_task(response.task_uid)
    response = await index.add_documents(small_movies)
    await async_client.wait_for_task(response.task_uid)
    response = await async_client.get_tasks(reverse=True)
    assert len(response.results) >= current_tasks


@pytest.mark.no_parallel
async def test_get_tasks_for_index_reverse(async_client, async_empty_index, small_movies):
    index = await async_empty_index()
    tasks = await async_client.get_tasks(index_ids=[index.uid])
    current_tasks = len(tasks.results)
    response = await index.add_documents(small_movies)
    await async_client.wait_for_task(response.task_uid)
    response = await index.add_documents(small_movies)
    await async_client.wait_for_task(response.task_uid)
    response = await async_client.get_tasks(index_ids=[index.uid], reverse=True)
    assert len(response.results) >= current_tasks
    uid = set([x.index_uid for x in response.results])
    assert len(uid) == 1
    assert next(iter(uid)) == index.uid


@pytest.mark.no_parallel
async def test_get_task(async_client, async_empty_index, small_movies):
    index = await async_empty_index()
    response = await index.add_documents(small_movies)
    await async_client.wait_for_task(response.task_uid)
    update = await async_client.get_task(response.task_uid)
    assert update.status == "succeeded"


@pytest.mark.no_parallel
async def test_wait_for_task(async_client, async_empty_index, small_movies):
    index = await async_empty_index()
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid)
    assert update.status == "succeeded"


@pytest.mark.no_parallel
async def test_wait_for_task_no_timeout(async_client, async_empty_index, small_movies):
    index = await async_empty_index()
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid, timeout_in_ms=None)
    assert update.status == "succeeded"


@pytest.mark.no_parallel
async def test_wait_for_pending_update_time_out(async_client, async_empty_index, small_movies):
    index = await async_empty_index()
    with pytest.raises(MeilisearchTimeoutError):
        response = await index.add_documents(small_movies)
        await async_client.wait_for_task(response.task_uid, timeout_in_ms=1, interval_in_ms=1)

    await async_client.wait_for_task(  # Make sure the indexing finishes so subsequent tests don't have issues.
        response.task_uid
    )


@pytest.mark.no_parallel
async def test_wait_for_task_raise_for_status_true(async_client, async_empty_index, small_movies):
    index = await async_empty_index()
    response = await index.add_documents(small_movies)
    update = await async_client.wait_for_task(response.task_uid, raise_for_status=True)
    assert update.status == "succeeded"


@pytest.mark.no_parallel
async def test_wait_for_task_raise_for_status_true_no_timeout(
    async_client, async_empty_index, small_movies, base_url, monkeypatch
):
    async def mock_get_response(*args, **kwargs):
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

    index = await async_empty_index()
    response = await index.add_documents(small_movies)
    monkeypatch.setattr(HttpxAsyncClient, "get", mock_get_response)
    with pytest.raises(MeilisearchTaskFailedError):
        await async_client.wait_for_task(
            response.task_uid, raise_for_status=True, timeout_in_ms=None
        )


@pytest.mark.no_parallel
async def test_wait_for_task_raise_for_status_false(
    async_client, async_empty_index, small_movies, base_url, monkeypatch
):
    async def mock_get_response(*args, **kwargs):
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

    index = await async_empty_index()
    response = await index.add_documents(small_movies)
    monkeypatch.setattr(HttpxAsyncClient, "get", mock_get_response)
    with pytest.raises(MeilisearchTaskFailedError):
        await async_client.wait_for_task(response.task_uid, raise_for_status=True)


@pytest.mark.parametrize("http2, expected", [(True, "HTTP/2"), (False, "HTTP/1.1")])
async def test_http_version(http2, expected, master_key, ssl_verify, http2_enabled):
    if not http2_enabled:
        pytest.skip("HTTP/2 is not enabled")
    async with AsyncClient(
        "https://127.0.0.1:7700", master_key, http2=http2, verify=ssl_verify
    ) as client:
        response = await client.http_client.get("health")
        assert response.http_version == expected


async def test_get_batches(async_client, async_empty_index, small_movies):
    # Add documents to create batches
    index = await async_empty_index()
    tasks = await index.add_documents_in_batches(small_movies, batch_size=5)
    waits = [async_client.wait_for_task(x.task_uid) for x in tasks]
    await asyncio.gather(*waits)

    result = await async_client.get_batches()
    assert len(result.results) > 0


async def test_get_batches_with_params(async_client, async_empty_index, small_movies):
    # Add documents to create batches
    index = await async_empty_index()
    tasks = await index.add_documents_in_batches(small_movies, batch_size=5)
    waits = [async_client.wait_for_task(x.task_uid) for x in tasks]
    await asyncio.gather(*waits)

    result = await async_client.get_batches(uids=[task.task_uid for task in tasks])
    assert len(result.results) > 0


async def test_get_batch(async_client, async_empty_index, small_movies):
    # Add documents to create batches
    index = await async_empty_index()
    tasks = await index.add_documents_in_batches(small_movies, batch_size=5)
    waits = [async_client.wait_for_task(x.task_uid) for x in tasks]
    await asyncio.gather(*waits)
    task = await async_client.get_task(tasks[0].task_uid)

    result = await async_client.get_batch(task.batch_uid)

    assert result.uid == task.batch_uid


async def test_get_batch_not_found(async_client):
    with pytest.raises(BatchNotFoundError):
        await async_client.get_batch(999999999)


async def test_get_networks(async_client):
    response = await async_client.get_networks()

    assert isinstance(response, Network)


async def test_add_or_update_networks(async_client):
    network = Network(
        self_="remote_1",
        remotes={
            "remote_1": {"url": "http://localhost:7700", "searchApiKey": "xxxxxxxxxxxxxx"},
            "remote_2": {"url": "http://localhost:7720", "searchApiKey": "xxxxxxxxxxxxxxx"},
        },
    )
    response = await async_client.add_or_update_networks(network=network)

    assert response.self_ == "remote_1"
    assert len(response.remotes) >= 2
    assert "remote_1" in response.remotes
    assert "remote_2" in response.remotes
