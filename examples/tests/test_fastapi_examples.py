import pytest
from httpx import ASGITransport, AsyncClient

from examples.fastapi_example import app


@pytest.fixture
async def test_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://127.0.0.1:8000"
    ) as client:
        yield client


sample_documents = [
    {"id": "1", "title": "Inception", "genre": "Sci-Fi"},
    {"id": "2", "title": "The Matrix", "genre": "Sci-Fi"},
]


@pytest.mark.asyncio
async def test_get_index(test_client):
    response = await test_client.get("/documents")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_check_health(test_client):
    response = await test_client.get("/health")
    assert response.status_code == 200
    health = response.json()
    assert health["status"] == "available"


@pytest.mark.asyncio
async def test_get_documents(test_client):
    await test_client.delete("/documents")
    await test_client.post("/documents", json=sample_documents)

    response = await test_client.get("/documents")
    assert response.status_code == 200
    documents = response.json()["results"]
    assert len(documents) == len(sample_documents)
    assert documents[0]["id"] == sample_documents[0]["id"]


@pytest.mark.asyncio
async def test_add_documents(test_client):
    response = await test_client.post("/documents", json=sample_documents)
    assert response.status_code == 200
    task_info = response.json()
    assert isinstance(task_info, list)
    for task in task_info:
        assert task["status"] == "enqueued"


@pytest.mark.asyncio
async def test_search(test_client):
    search_params = {"q": "Inception"}
    response = await test_client.post("/search", json=search_params)
    assert response.status_code == 200
    search_results = response.json()
    assert len(search_results["hits"]) == 1
    assert search_results["hits"][0]["id"] == "1"
