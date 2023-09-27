from __future__ import annotations

from asyncio import sleep
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from httpx import AsyncClient as HttpxAsyncClient
from httpx import ConnectError, ConnectTimeout, RemoteProtocolError, Request, Response

from meilisearch_python_async import AsyncClient
from meilisearch_python_async.errors import (
    InvalidRestriction,
    MeilisearchApiError,
    MeilisearchCommunicationError,
)
from meilisearch_python_async.models.client import KeyCreate, KeyUpdate
from meilisearch_python_async.models.index import IndexInfo
from meilisearch_python_async.models.version import Version
from meilisearch_python_async.task import (
    async_get_task,
    async_wait_for_task,
)


@pytest.fixture
async def remove_default_search_key(default_search_key, async_test_client):
    await async_test_client.delete_key(default_search_key.key)
    yield
    key = KeyCreate(
        description=default_search_key.description,
        actions=default_search_key.actions,
        indexes=default_search_key.indexes,
        expires_at=default_search_key.expires_at,
    )
    await async_test_client.create_key(key)


@pytest.fixture
async def test_key(async_test_client):
    key_info = KeyCreate(description="test", actions=["search"], indexes=["movies"])
    key = await async_test_client.create_key(key_info)

    yield key

    try:
        await async_test_client.delete_key(key.key)
    except MeilisearchApiError:
        pass


@pytest.fixture
async def test_key_info(async_test_client):
    key_info = KeyCreate(description="test", actions=["search"], indexes=["movies"])

    yield key_info

    try:
        keys = await async_test_client.get_keys()
        key = next(x for x in keys.results if x.description == key_info.description)
        await async_test_client.delete_key(key.key)
    except MeilisearchApiError:
        pass


async def wait_for_dump_creation(
    async_test_client, dump_uid, timeout_in_ms=10000.0, interval_in_ms=500.0
):
    start_time = datetime.now()
    elapsed_time = 0.0
    while elapsed_time < timeout_in_ms:
        dump = await async_test_client.get_dump_status(dump_uid)
        if dump.status != "in_progress":
            return None
        await sleep(interval_in_ms / 1000)
        time_delta = datetime.now() - start_time
        elapsed_time = time_delta.seconds * 1000 + time_delta.microseconds / 1000
    raise TimeoutError


async def test_create_index_with_primary_key(async_test_client):
    uid = "test"
    primary_key = "pk_test"
    index = await async_test_client.create_index(uid=uid, primary_key=primary_key)

    assert index.uid == uid

    assert index.primary_key == primary_key
    assert isinstance(index.created_at, datetime)
    assert isinstance(index.updated_at, datetime)


async def test_create_index_no_primary_key(async_test_client):
    uid = "test"
    index = await async_test_client.create_index(uid=uid)

    assert index.uid == uid

    assert index.primary_key is None
    assert isinstance(index.created_at, datetime)
    assert isinstance(index.updated_at, datetime)


async def test_create_keys_with_wildcarded_actions(async_test_client, test_key_info):
    test_key_info.actions = ["documents.*"]
    key = await async_test_client.create_key(test_key_info)

    assert key.actions == ["documents.*"]


async def test_generate_tenant_token_custom_key(async_test_client, test_key):
    search_rules = {"test": "value"}
    expected = {"searchRules": search_rules, "apiKeyUid": test_key.uid}
    token = async_test_client.generate_tenant_token(search_rules, api_key=test_key)
    assert expected == jwt.decode(jwt=token, key=test_key.key, algorithms=["HS256"])


async def test_generate_tenant_token_default_key(async_test_client, default_search_key):
    search_rules = {"test": "value"}
    expected = {"searchRules": search_rules, "apiKeyUid": default_search_key.uid}
    token = async_test_client.generate_tenant_token(search_rules, api_key=default_search_key)
    assert expected == jwt.decode(jwt=token, key=default_search_key.key, algorithms=["HS256"])


async def test_generate_tenant_token_default_key_expires(async_test_client, default_search_key):
    search_rules: dict[str, Any] = {"test": "value"}
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=1)
    expected: dict[str, Any] = {"searchRules": search_rules}
    expected["apiKeyUid"] = default_search_key.uid
    expected["exp"] = int(datetime.timestamp(expires_at))
    token = async_test_client.generate_tenant_token(
        search_rules, api_key=default_search_key, expires_at=expires_at
    )
    assert expected == jwt.decode(jwt=token, key=default_search_key.key, algorithms=["HS256"])


async def test_generate_tenant_token_default_key_expires_past(
    async_test_client, default_search_key
):
    search_rules: dict[str, Any] = {"test": "value"}
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=-1)
    with pytest.raises(ValueError):
        async_test_client.generate_tenant_token(
            search_rules, api_key=default_search_key, expires_at=expires_at
        )


async def test_generate_tenant_token_invalid_restriction(test_key_info, async_test_client):
    test_key_info.indexes = ["good"]
    key = await async_test_client.create_key(test_key_info)
    payload = {"indexes": ["bad"]}

    with pytest.raises(InvalidRestriction):
        async_test_client.generate_tenant_token(payload, api_key=key)


@pytest.mark.usefixtures("async_indexes_sample")
async def test_get_indexes(async_test_client, index_uid, index_uid2):
    response = await async_test_client.get_indexes()
    response_uids = [x.uid for x in response]

    assert index_uid in response_uids
    assert index_uid2 in response_uids
    assert len(response) == 2


@pytest.mark.usefixtures("async_indexes_sample")
async def test_get_indexes_offset_and_limit(async_test_client):
    response = await async_test_client.get_indexes(offset=1, limit=1)
    assert len(response) == 1


@pytest.mark.usefixtures("async_indexes_sample")
async def test_get_indexes_offset(async_test_client):
    response = await async_test_client.get_indexes(offset=1)
    assert len(response) >= 1 and len(response) <= 20


@pytest.mark.usefixtures("async_indexes_sample")
async def test_get_indexes_limit(async_test_client):
    response = await async_test_client.get_indexes(limit=1)
    assert len(response) == 1


async def test_get_indexes_none(async_test_client):
    response = await async_test_client.get_indexes()

    assert response is None


@pytest.mark.usefixtures("async_indexes_sample")
async def test_get_index(async_test_client, index_uid):
    response = await async_test_client.get_index(index_uid)

    assert response.uid == index_uid
    assert response.primary_key is None
    assert isinstance(response.created_at, datetime)
    assert isinstance(response.updated_at, datetime)


async def test_get_index_not_found(async_test_client):
    with pytest.raises(MeilisearchApiError):
        await async_test_client.get_index("test")


def test_index(async_test_client):
    uid = "test"
    response = async_test_client.index(uid)

    assert response.uid == uid


async def test_get_or_create_index_with_primary_key(async_test_client):
    primary_key = "pk_test"
    uid = "test1"
    response = await async_test_client.get_or_create_index(uid, primary_key)

    assert response.uid == uid
    assert response.primary_key == primary_key


async def test_get_or_create_index_no_primary_key(async_test_client):
    uid = "test"
    response = await async_test_client.get_or_create_index(uid)

    assert response.uid == uid
    assert response.primary_key is None


async def test_get_or_create_index_communication_error(async_test_client, monkeypatch):
    async def mock_get_response(*args, **kwargs):
        raise ConnectError("test", request=Request("GET", url="http://localhost"))

    async def mock_post_response(*args, **kwargs):
        raise ConnectError("test", request=Request("POST", url="http://localhost"))

    monkeypatch.setattr(HttpxAsyncClient, "get", mock_get_response)
    monkeypatch.setattr(HttpxAsyncClient, "post", mock_post_response)
    with pytest.raises(MeilisearchCommunicationError):
        await async_test_client.get_or_create_index("test")


async def test_get_or_create_index_api_error(async_test_client, monkeypatch):
    async def mock_response(*args, **kwargs):
        raise MeilisearchApiError("test", Response(status_code=404))

    monkeypatch.setattr(AsyncClient, "get_index", mock_response)
    with pytest.raises(MeilisearchApiError):
        await async_test_client.get_or_create_index("test")


@pytest.mark.usefixtures("async_indexes_sample")
async def test_get_all_stats(async_test_client, index_uid, index_uid2):
    response = await async_test_client.get_all_stats()

    assert index_uid in response.indexes
    assert index_uid2 in response.indexes


@pytest.mark.usefixtures("async_indexes_sample")
async def test_get_raw_index(async_test_client, index_uid):
    response = await async_test_client.get_raw_index(index_uid)

    assert response.uid == index_uid
    assert isinstance(response, IndexInfo)


async def test_get_raw_index_none(async_test_client):
    response = await async_test_client.get_raw_index("test")

    assert response is None


@pytest.mark.usefixtures("async_indexes_sample")
async def test_get_raw_indexes(async_test_client, index_uid, index_uid2):
    response = await async_test_client.get_raw_indexes()
    response_uids = [x.uid for x in response]

    assert index_uid in response_uids
    assert index_uid2 in response_uids
    assert len(response) == 2


@pytest.mark.usefixtures("async_indexes_sample")
async def test_get_raw_indexes_offset_and_limit(async_test_client):
    response = await async_test_client.get_raw_indexes(offset=1, limit=1)
    assert len(response) == 1


@pytest.mark.usefixtures("async_indexes_sample")
async def test_get_raw_indexes_offset(async_test_client):
    response = await async_test_client.get_raw_indexes(offset=1)
    assert len(response) >= 1 and len(response) <= 20


@pytest.mark.usefixtures("async_indexes_sample")
async def test_get_raw_indexes_limit(async_test_client):
    response = await async_test_client.get_raw_indexes(limit=1)
    assert len(response) == 1


async def test_get_raw_indexes_none(async_test_client):
    response = await async_test_client.get_raw_indexes()

    assert response is None


async def test_health(async_test_client):
    health = await async_test_client.health()

    assert health.status == "available"


async def test_create_key(test_key_info, async_test_client):
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=2)
    test_key_info.expires_at = expires_at
    key = await async_test_client.create_key(test_key_info)

    assert key.description == test_key_info.description
    assert key.actions == test_key_info.actions
    assert key.indexes == test_key_info.indexes
    assert key.expires_at == expires_at.replace(tzinfo=None)


async def test_create_key_no_expires(test_key_info, async_test_client):
    key = await async_test_client.create_key(test_key_info)

    assert key.description == test_key_info.description
    assert key.actions == test_key_info.actions
    assert key.indexes == test_key_info.indexes
    assert key.expires_at is None


async def test_delete_key(test_key, async_test_client):
    result = await async_test_client.delete_key(test_key.key)
    assert result == 204

    with pytest.raises(MeilisearchApiError):
        await async_test_client.get_key(test_key.key)


async def test_get_keys(async_test_client):
    response = await async_test_client.get_keys()
    assert len(response.results) == 2


async def test_get_keys_offset_and_limit(async_test_client):
    response = await async_test_client.get_keys(offset=1, limit=1)
    assert len(response.results) == 1


async def test_get_keys_offset(async_test_client):
    response = await async_test_client.get_keys(offset=1)
    assert len(response.results) >= 1 and len(response.results) <= 20


async def test_get_keys_limit(async_test_client):
    response = await async_test_client.get_keys(limit=1)
    assert len(response.results) == 1


async def test_get_key(test_key, async_test_client):
    key = await async_test_client.get_key(test_key.key)
    assert key.description == test_key.description


async def test_update_key(test_key, async_test_client):
    update_key_info = KeyUpdate(
        key=test_key.key,
        description="updated",
    )

    key = await async_test_client.update_key(update_key_info)

    assert key.description == update_key_info.description
    assert key.actions == test_key.actions
    assert key.indexes == test_key.indexes
    assert key.expires_at == test_key.expires_at


async def test_get_version(async_test_client):
    response = await async_test_client.get_version()

    assert isinstance(response, Version)


async def test_create_dump(async_test_client, async_index_with_documents):
    index = await async_index_with_documents()

    response = await async_test_client.create_dump()

    await async_wait_for_task(index.http_client, response.task_uid)

    dump_status = await async_get_task(index.http_client, response.task_uid)
    assert dump_status.status == "succeeded"
    assert dump_status.task_type == "dumpCreation"


async def test_no_master_key(base_url):
    with pytest.raises(MeilisearchApiError):
        async with AsyncClient(base_url) as client:
            await client.create_index("some_index")


async def test_bad_master_key(base_url, master_key):
    with pytest.raises(MeilisearchApiError):
        async with AsyncClient(base_url) as client:
            await client.create_index("some_index", f"{master_key}bad")


async def test_communication_error(master_key):
    with pytest.raises(MeilisearchCommunicationError):
        async with AsyncClient("http://wrongurl:1234", master_key, timeout=1) as client:
            await client.create_index("some_index")


async def test_remote_protocol_error(async_test_client, monkeypatch):
    def mock_error(*args, **kwargs):
        raise RemoteProtocolError("error", request=args[0])

    monkeypatch.setattr(HttpxAsyncClient, "post", mock_error)
    with pytest.raises(MeilisearchCommunicationError):
        await async_test_client.create_index("some_index")


async def test_connection_timeout(async_test_client, monkeypatch):
    def mock_error(*args, **kwargs):
        raise ConnectTimeout("error")

    monkeypatch.setattr(HttpxAsyncClient, "post", mock_error)
    with pytest.raises(MeilisearchCommunicationError):
        await async_test_client.create_index("some_index")


async def test_swap_indexes(async_test_client, async_empty_index):
    index_a = await async_empty_index()
    index_b = await async_empty_index()
    task_a = await index_a.add_documents([{"id": 1, "title": index_a.uid}])
    task_b = await index_b.add_documents([{"id": 1, "title": index_b.uid}])
    await async_wait_for_task(index_a.http_client, task_a.task_uid)
    await async_wait_for_task(index_b.http_client, task_b.task_uid)
    swapTask = await async_test_client.swap_indexes([(index_a.uid, index_b.uid)])
    task = await async_wait_for_task(index_a.http_client, swapTask.task_uid)
    doc_a = await async_test_client.index(index_a.uid).get_document(1)
    doc_b = await async_test_client.index(index_b.uid).get_document(1)

    assert doc_a["title"] == index_b.uid
    assert doc_b["title"] == index_a.uid
    assert task.task_type == "indexSwap"