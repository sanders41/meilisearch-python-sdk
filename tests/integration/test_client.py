from asyncio import sleep
from datetime import datetime

import pytest
from httpx import AsyncClient, ConnectError, ConnectTimeout, RemoteProtocolError, Response

from async_search_client.client import Client
from async_search_client.errors import MeiliSearchApiError, MeiliSearchCommunicationError
from async_search_client.models import DumpInfo, Version


async def wait_for_dump_creation(test_client, dump_uid, timeout_in_ms=10000, interval_in_ms=500):
    start_time = datetime.now()
    elapsed_time = 0
    while elapsed_time < timeout_in_ms:
        dump = await test_client.get_dump_status(dump_uid)
        if dump.status != "in_progress":
            return None
        await sleep(interval_in_ms / 1000)
        time_delta = datetime.now() - start_time
        elapsed_time = time_delta.seconds * 1000 + time_delta.microseconds / 1000
    raise TimeoutError


@pytest.mark.asyncio
@pytest.mark.parametrize("primary_key", ["pk_test", None])
async def test_create_index(test_client, primary_key):
    uid = "test"
    index = await test_client.create_index(uid, primary_key)

    assert index.uid == uid

    if primary_key:
        assert index.primary_key == primary_key
    else:
        assert index.primary_key is None


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
@pytest.mark.parametrize("uid, primary_key", [("test1", "pk_test"), ("test2", None)])
async def test_get_or_create_index(test_client, uid, primary_key):
    response = await test_client.get_or_create_index(uid, primary_key)

    assert response.uid == uid

    if primary_key:
        assert response.primary_key == primary_key
    else:
        assert response.primary_key is None


@pytest.mark.asyncio
async def test_get_or_create_index_communication_error(test_client, monkeypatch):
    async def mock_get_response(*args, **kwargs):
        raise ConnectError("test", request="GET")

    async def mock_post_response(*args, **kwargs):
        raise ConnectError("test", request="POST")

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
async def test_health(test_client):
    health = await test_client.health()

    assert health.status == "available"


@pytest.mark.asyncio
async def test_get_keys(test_client):
    response = await test_client.get_keys()

    assert response.public is not None
    assert response.private is not None


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
        async with Client("http://wrongurl:1234", master_key, 1) as client:
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
