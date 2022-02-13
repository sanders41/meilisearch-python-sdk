from asyncio import sleep
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient, ConnectError, ConnectTimeout, RemoteProtocolError, Request, Response

from meilisearch_python_async.client import Client
from meilisearch_python_async.errors import MeiliSearchApiError, MeiliSearchCommunicationError
from meilisearch_python_async.models.client import KeyCreate, KeyUpdate
from meilisearch_python_async.models.dump import DumpInfo
from meilisearch_python_async.models.index import IndexInfo
from meilisearch_python_async.models.version import Version


@pytest.fixture
@pytest.mark.asyncio
async def test_key(test_client):
    key_info = KeyCreate(description="test", actions=["search"], indexes=["movies"])

    key = await test_client.create_key(key_info)

    yield key

    try:
        await test_client.delete_key(key.key)
    except MeiliSearchApiError:
        pass


@pytest.fixture
@pytest.mark.asyncio
async def test_key_info(test_client):
    key_info = KeyCreate(description="test", actions=["search"], indexes=["movies"])

    yield key_info

    try:
        keys = await test_client.get_keys()
        key = next(x for x in keys if x.description == key_info.description)
        await test_client.delete_key(key.key)
    except MeiliSearchApiError:
        pass


async def wait_for_dump_creation(
    test_client, dump_uid, timeout_in_ms=10000.0, interval_in_ms=500.0
):
    start_time = datetime.now()
    elapsed_time = 0.0
    while elapsed_time < timeout_in_ms:
        dump = await test_client.get_dump_status(dump_uid)
        if dump.status != "in_progress":
            return None
        await sleep(interval_in_ms / 1000)
        time_delta = datetime.now() - start_time
        elapsed_time = time_delta.seconds * 1000 + time_delta.microseconds / 1000
    raise TimeoutError


@pytest.mark.asyncio
async def test_create_index_with_primary_key(test_client):
    uid = "test"
    primary_key = "pk_test"
    index = await test_client.create_index(uid=uid, primary_key=primary_key)

    assert index.uid == uid

    assert index.primary_key == primary_key
    assert isinstance(index.created_at, datetime)
    assert isinstance(index.updated_at, datetime)


@pytest.mark.asyncio
async def test_create_index_no_primary_key(test_client):
    uid = "test"
    index = await test_client.create_index(uid=uid)

    assert index.uid == uid

    assert index.primary_key is None
    assert isinstance(index.created_at, datetime)
    assert isinstance(index.updated_at, datetime)


@pytest.mark.asyncio
@pytest.mark.usefixtures("indexes_sample")
async def test_get_indexes(test_client, index_uid, index_uid2):
    response = await test_client.get_indexes()
    response_uids = [x.uid for x in response]

    assert index_uid in response_uids
    assert index_uid2 in response_uids
    assert len(response) == 2


@pytest.mark.asyncio
async def test_get_indexes_none(test_client):
    response = await test_client.get_indexes()

    assert response is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("indexes_sample")
async def test_get_index(test_client, index_uid):
    response = await test_client.get_index(index_uid)

    assert response.uid == index_uid
    assert response.primary_key is None
    assert isinstance(response.created_at, datetime)
    assert isinstance(response.updated_at, datetime)


@pytest.mark.asyncio
async def test_get_index_not_found(test_client):
    with pytest.raises(MeiliSearchApiError):
        await test_client.get_index("test")


def test_index(test_client):
    uid = "test"
    response = test_client.index(uid)

    assert response.uid == uid


@pytest.mark.asyncio
async def test_get_or_create_index_with_primary_key(test_client):
    primary_key = "pk_test"
    uid = "test1"
    response = await test_client.get_or_create_index(uid, primary_key)

    assert response.uid == uid
    assert response.primary_key == primary_key


@pytest.mark.asyncio
async def test_get_or_create_index_no_primary_key(test_client):
    uid = "test"
    response = await test_client.get_or_create_index(uid)

    assert response.uid == uid
    assert response.primary_key is None


@pytest.mark.asyncio
async def test_get_or_create_index_communication_error(test_client, monkeypatch):
    async def mock_get_response(*args, **kwargs):
        raise ConnectError("test", request=Request("GET", url="http://localhost"))

    async def mock_post_response(*args, **kwargs):
        raise ConnectError("test", request=Request("POST", url="http://localhost"))

    monkeypatch.setattr(AsyncClient, "get", mock_get_response)
    monkeypatch.setattr(AsyncClient, "post", mock_post_response)
    with pytest.raises(MeiliSearchCommunicationError):
        await test_client.get_or_create_index("test")


@pytest.mark.asyncio
async def test_get_or_create_index_api_error(test_client, monkeypatch):
    async def mock_response(*args, **kwargs):
        raise MeiliSearchApiError("test", Response(status_code=404))

    monkeypatch.setattr(Client, "get_index", mock_response)
    with pytest.raises(MeiliSearchApiError):
        await test_client.get_or_create_index("test")


@pytest.mark.asyncio
@pytest.mark.usefixtures("indexes_sample")
async def test_get_all_stats(test_client, index_uid, index_uid2):
    response = await test_client.get_all_stats()

    assert index_uid in response.indexes
    assert index_uid2 in response.indexes


@pytest.mark.asyncio
@pytest.mark.usefixtures("indexes_sample")
async def test_get_raw_index(test_client, index_uid):
    response = await test_client.get_raw_index(index_uid)

    assert response.uid == index_uid
    assert isinstance(response, IndexInfo)


@pytest.mark.asyncio
async def test_get_raw_index_none(test_client):
    response = await test_client.get_raw_index("test")

    assert response is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("indexes_sample")
async def test_get_raw_indexes(test_client, index_uid, index_uid2):
    response = await test_client.get_raw_indexes()
    response_uids = [x.uid for x in response]

    assert index_uid in response_uids
    assert index_uid2 in response_uids
    assert len(response) == 2


@pytest.mark.asyncio
async def test_get_raw_indexes_none(test_client):
    response = await test_client.get_raw_indexes()

    assert response is None


@pytest.mark.asyncio
async def test_health(test_client):
    health = await test_client.health()

    assert health.status == "available"


@pytest.mark.asyncio
async def test_create_key(test_key_info, test_client):
    expires_at = datetime.utcnow() + timedelta(days=2)
    test_key_info.expires_at = expires_at
    key = await test_client.create_key(test_key_info)

    assert key.description == test_key_info.description
    assert key.actions == test_key_info.actions
    assert key.indexes == test_key_info.indexes
    assert key.expires_at.date() == expires_at.date()


@pytest.mark.asyncio
async def test_create_key_no_expires(test_key_info, test_client):
    key = await test_client.create_key(test_key_info)

    assert key.description == test_key_info.description
    assert key.actions == test_key_info.actions
    assert key.indexes == test_key_info.indexes
    assert key.expires_at is None


@pytest.mark.asyncio
async def test_delete_key(test_key, test_client):
    result = await test_client.delete_key(test_key.key)
    assert result == 204

    with pytest.raises(MeiliSearchApiError):
        await test_client.get_key(test_key.key)


@pytest.mark.asyncio
async def test_get_keys(test_client):
    response = await test_client.get_keys()

    assert len(response) == 2


@pytest.mark.asyncio
async def test_get_key(test_key, test_client):
    key = await test_client.get_key(test_key.key)
    assert key.description == test_key.description


@pytest.mark.asyncio
async def test_update_key(test_key, test_client):
    update_key_info = KeyUpdate(
        key=test_key.key,
        description="updated",
        actions=["*"],
        indexes=["*"],
        expires_at=datetime.utcnow() + timedelta(days=2),
    )

    key = await test_client.update_key(update_key_info)

    assert key.description == update_key_info.description
    assert key.actions == update_key_info.actions
    assert key.indexes == update_key_info.indexes
    assert key.expires_at.date() == update_key_info.expires_at.date()  # type: ignore


@pytest.mark.asyncio
async def test_get_version(test_client):
    response = await test_client.get_version()

    assert isinstance(response, Version)


@pytest.mark.asyncio
async def test_create_dump(test_client, index_with_documents):
    await index_with_documents("indexUID-dump-creation")

    response = await test_client.create_dump()
    assert response.status == "in_progress"
    complete = await wait_for_dump_creation(test_client, response.uid)

    assert complete is None


@pytest.mark.asyncio
async def test_get_dump_status(test_client, index_with_documents):
    await index_with_documents("indexUID-dump-status")
    dump = await test_client.create_dump()

    assert dump.status == "in_progress"

    dump_status = await test_client.get_dump_status(dump.uid)
    assert isinstance(dump_status, DumpInfo)

    complete = await wait_for_dump_creation(test_client, dump.uid)

    assert complete is None


@pytest.mark.asyncio
async def test_get_dump_status_error(test_client):
    with pytest.raises(MeiliSearchApiError):
        await test_client.get_dump_status("bad")


@pytest.mark.asyncio
async def test_no_master_key(base_url):
    with pytest.raises(MeiliSearchApiError):
        async with Client(base_url) as client:
            await client.create_index("some_index")


@pytest.mark.asyncio
async def test_bad_master_key(base_url, master_key):
    with pytest.raises(MeiliSearchApiError):
        async with Client(base_url) as client:
            await client.create_index("some_index", f"{master_key}bad")


@pytest.mark.asyncio
async def test_communication_error(master_key):
    with pytest.raises(MeiliSearchCommunicationError):
        async with Client("http://wrongurl:1234", master_key, timeout=1) as client:
            await client.create_index("some_index")


@pytest.mark.asyncio
async def test_remote_protocol_error(test_client, monkeypatch):
    def mock_error(*args, **kwargs):
        raise RemoteProtocolError("error", request=args[0])

    monkeypatch.setattr(AsyncClient, "post", mock_error)
    with pytest.raises(MeiliSearchCommunicationError):
        await test_client.create_index("some_index")


@pytest.mark.asyncio
async def test_connection_timeout(test_client, monkeypatch):
    def mock_error(*args, **kwargs):
        raise ConnectTimeout("error")

    monkeypatch.setattr(AsyncClient, "post", mock_error)
    with pytest.raises(MeiliSearchCommunicationError):
        await test_client.create_index("some_index")
