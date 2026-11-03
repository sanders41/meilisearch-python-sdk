from uuid import uuid4

import pytest
from httpx2 import AsyncClient, Client, MockTransport, Response

from meilisearch_python_sdk._http_requests import AsyncHttpRequests, HttpRequests, user_agent
from meilisearch_python_sdk.json_handler import BuiltinHandler


async def test_async_empty_bytes_compressed(async_client):
    index = async_client.index(str(uuid4()))
    response = await index._http_requests.post(
        index._documents_url, body=b"''", content_type="text/csv", compress=True
    )

    assert response.status_code == 202


async def test_async_empty_byte_array_compressed(async_client):
    index = async_client.index(str(uuid4()))
    b = bytearray(b"''")
    response = await index._http_requests.post(
        index._documents_url, body=b, content_type="text/csv", compress=True
    )

    assert response.status_code == 202


def test_empty_bytes_compressed(client):
    index = client.index(str(uuid4()))
    response = index._http_requests.post(
        index._documents_url, body=b"''", content_type="text/csv", compress=True
    )

    assert response.status_code == 202


def test_empty_byte_array_compressed(client):
    index = client.index(str(uuid4()))
    b = bytearray(b"''")
    response = index._http_requests.post(
        index._documents_url, body=b, content_type="text/csv", compress=True
    )

    assert response.status_code == 202


async def test_async_unsupported_body_type(async_client):
    index = async_client.index(str(uuid4()))
    with pytest.raises(TypeError, match="Unsupported body type for text/csv: dict"):
        await index._http_requests.post(
            index._documents_url, body={"id": 1}, content_type="text/csv"
        )


def test_unsupported_body_type(client):
    index = client.index(str(uuid4()))
    with pytest.raises(TypeError, match="Unsupported body type for text/csv: dict"):
        index._http_requests.post(index._documents_url, body={"id": 1}, content_type="text/csv")


@pytest.mark.parametrize("method", ("get", "delete"))
async def test_async_user_agent_without_body(method):
    seen = []
    transport = MockTransport(lambda r: seen.append(r.headers["user-agent"]) or Response(200))
    async with AsyncClient(base_url="http://test", transport=transport) as http_client:
        await getattr(AsyncHttpRequests(http_client, BuiltinHandler()), method)("indexes")

    assert seen == [user_agent()]


@pytest.mark.parametrize("method", ("get", "delete"))
def test_user_agent_without_body(method):
    seen = []
    transport = MockTransport(lambda r: seen.append(r.headers["user-agent"]) or Response(200))
    with Client(base_url="http://test", transport=transport) as http_client:
        getattr(HttpRequests(http_client, BuiltinHandler()), method)("indexes")

    assert seen == [user_agent()]
