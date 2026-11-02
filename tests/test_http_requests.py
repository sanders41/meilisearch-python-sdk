from uuid import uuid4

import pytest


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
