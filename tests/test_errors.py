from httpx import Response

from meilisearch_python_async.errors import (
    MeiliSearchApiError,
    MeiliSearchCommunicationError,
    MeiliSearchError,
    MeiliSearchTimeoutError,
)


def test_meilisearch_api_error():
    expected = "test"
    got = MeiliSearchApiError(expected, Response(status_code=404))

    assert expected in str(got)


def test_meilisearch_communication_error():
    expected = "test"
    got = MeiliSearchCommunicationError(expected)

    assert expected in str(got)


def test_meilisearch_error():
    expected = "test message"
    got = MeiliSearchError(expected)

    assert expected in str(got)


def test_meilisearch_timeout_error():
    expected = "test"
    got = MeiliSearchTimeoutError(expected)

    assert expected in str(got)
