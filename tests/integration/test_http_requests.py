import pytest

from meilisearch_python_async._http_requests import _HttpRequests


@pytest.mark.asyncio
async def test_content_type_none(test_client):
    http_request = _HttpRequests(test_client._http_client)

    response = await http_request.post(
        "/indexes/test/documents", body=[{"test": "value"}], content_type=None
    )

    assert response
