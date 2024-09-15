from pathlib import Path
from uuid import uuid4

import pytest
from pytest_asyncio import is_async_test

from meilisearch_python_sdk import AsyncClient, Client

MASTER_KEY = "masterKey"

ROOT_PATH = Path().absolute()
SMALL_MOVIES_PATH = ROOT_PATH.parent / "datasets" / "small_movies.json"


def pytest_collection_modifyitems(items):
    pytest_asyncio_tests = (item for item in items if is_async_test(item))
    session_scope_marker = pytest.mark.asyncio(loop_scope="session")
    for async_test in pytest_asyncio_tests:
        async_test.add_marker(session_scope_marker, append=False)


@pytest.fixture(scope="session")
def base_url():
    return "http://127.0.0.1:7700"


@pytest.fixture(scope="session")
async def async_client(base_url):
    async with AsyncClient(base_url, MASTER_KEY) as client:
        yield client


@pytest.fixture(scope="session")
def client(base_url):
    yield Client(base_url, MASTER_KEY)


@pytest.fixture(scope="session")
def small_movies_path():
    return SMALL_MOVIES_PATH


@pytest.fixture
async def async_empty_index(async_client):
    async def index_maker():
        return await async_client.create_index(uid=str(uuid4()), timeout_in_ms=5000)

    return index_maker


@pytest.fixture
def empty_index(client):
    def index_maker():
        return client.create_index(uid=str(uuid4()), timeout_in_ms=5000)

    return index_maker
