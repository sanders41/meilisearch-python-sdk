import pytest
from httpx import AsyncClient as HttpxAsyncClient
from httpx import Client as HttpxClient
from httpx import HTTPStatusError, Request, Response

from meilisearch_python_sdk.errors import (
    MeilisearchApiError,
    MeilisearchCommunicationError,
    MeilisearchError,
    MeilisearchTaskFailedError,
    MeilisearchTimeoutError,
)


def test_meilisearch_api_error():
    expected = "test"
    got = MeilisearchApiError(expected, Response(status_code=404))

    assert expected in str(got)


def test_meilisearch_communication_error():
    expected = "test"
    got = MeilisearchCommunicationError(expected)

    assert expected in str(got)


def test_meilisearch_error():
    expected = "test message"
    got = MeilisearchError(expected)

    assert expected in str(got)


def test_meilisearch_task_failed_error():
    expected = "test message"
    got = MeilisearchTaskFailedError(expected)

    assert expected in str(got)


def test_meilisearch_timeout_error():
    expected = "test"
    got = MeilisearchTimeoutError(expected)

    assert expected in str(got)


async def test_non_json_error_async(async_index_with_documents, monkeypatch):
    async def mock_post_response(*args, **kwargs):
        return Response(
            status_code=504, text="test", request=Request("POST", url="http://localhost")
        )

    monkeypatch.setattr(HttpxAsyncClient, "post", mock_post_response)
    with pytest.raises(HTTPStatusError):
        await async_index_with_documents()


def test_non_json_error(index_with_documents, monkeypatch):
    def mock_post_response(*args, **kwargs):
        return Response(
            status_code=504, text="test", request=Request("POST", url="http://localhost")
        )

    monkeypatch.setattr(HttpxClient, "post", mock_post_response)
    with pytest.raises(HTTPStatusError):
        index_with_documents()
