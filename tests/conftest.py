import asyncio
import json
import socket

import docker
import pytest

from async_search_client.client import Client

MASTER_KEY = "masterKey"
BASE_URL = "http://127.0.0.1:7700"
INDEX_UID = "indexUID"
INDEX_UID2 = "indexUID2"
INDEX_UID3 = "indexUID3"
INDEX_UID4 = "indexUID4"

INDEX_FIXTURE = [
    {"uid": INDEX_UID},
    {"uid": INDEX_UID2, "primary_key": "book_id"},
]


@pytest.fixture(scope="session", autouse=True)
def meilisearch_docker():
    """
    Check if something is already running on port 7700, and if so assume meilisearch is running
    already. If not start a meilisearch docker container for testing.
    """

    PORT = 7700
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("localhost", PORT)) != 0:
            client = docker.from_env()
            container = client.containers.run(
                image="getmeili/meilisearch:latest",
                command="./meilisearch --master-key=masterKey --no-analytics=true",
                ports={"7700": 7700},
                tty=True,
                remove=True,
                detach=True,
            )
            yield container
            container.stop()
        else:
            yield


@pytest.fixture(scope="session", autouse=True)
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
@pytest.fixture(scope="session")
async def test_client():
    async with Client(BASE_URL, MASTER_KEY) as client:
        yield client


@pytest.mark.asyncio
@pytest.fixture(autouse=True)
async def clear_indexes(test_client):
    """
    Auto-clears the indexes after each test function run.
    Makes all the test functions independent.
    """
    yield
    indexes = await test_client.get_indexes()
    if indexes:
        for index in indexes:
            await test_client.index(index.uid).delete()


@pytest.fixture(scope="session")
def master_key():
    return MASTER_KEY


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture
def index_uid():
    return INDEX_UID


@pytest.fixture
def index_uid2():
    return INDEX_UID2


@pytest.fixture
def index_uid3():
    return INDEX_UID3


@pytest.fixture
def index_uid4():
    return INDEX_UID4


@pytest.mark.asyncio
@pytest.fixture
async def indexes_sample(test_client):
    indexes = []
    for index_args in INDEX_FIXTURE:
        index = await test_client.create_index(**index_args)
        indexes.append(index)
    yield indexes


@pytest.fixture(scope="session")
def small_movies():
    """
    Runs once per session. Provides the content of small_movies.json.
    """
    with open("./datasets/small_movies.json", "r") as movie_file:
        yield json.loads(movie_file.read())


@pytest.mark.asyncio
@pytest.fixture
async def empty_index(test_client):
    async def index_maker(index_name=INDEX_UID):
        return await test_client.create_index(uid=index_name)

    return index_maker


@pytest.mark.asyncio
@pytest.fixture
async def index_with_documents(empty_index, small_movies, index_uid):
    async def index_maker(index_name=index_uid, documents=small_movies):
        index = await empty_index(index_name)
        response = await index.add_documents(documents)
        await index.wait_for_pending_update(response.update_id)
        return index

    return index_maker
