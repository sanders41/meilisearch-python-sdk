import asyncio
import csv
import json
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import AsyncClient as HttpxAsyncClient

from meilisearch_python_sdk import AsyncClient, Client
from meilisearch_python_sdk._task import async_wait_for_task, wait_for_task
from meilisearch_python_sdk.models.settings import (
    Embedders,
    Faceting,
    MeilisearchSettings,
    Pagination,
    ProximityPrecision,
    TypoTolerance,
    UserProvidedEmbedder,
)

MASTER_KEY = "masterKey"
BASE_URL = "http://127.0.0.1:7700"

ROOT_PATH = Path().absolute()
SMALL_MOVIES_PATH = ROOT_PATH / "datasets" / "small_movies.json"


@pytest.fixture
async def async_client():
    async with AsyncClient(BASE_URL, MASTER_KEY) as client:
        yield client


@pytest.fixture
async def async_client_with_plugins():
    async with AsyncClient(BASE_URL, MASTER_KEY) as client:
        yield client


@pytest.fixture
def client():
    yield Client(BASE_URL, MASTER_KEY)


@pytest.fixture(autouse=True)
async def clear_indexes(async_client, request, pytestconfig):
    """Auto-clears the indexes after each test function run if not a parallel test."""
    if "no_parallel" in request.keywords and "not no_parallel" not in request.keywords:
        indexes = await async_client.get_indexes()
        if indexes:
            tasks = await asyncio.gather(*[async_client.index(x.uid).delete() for x in indexes])
            await asyncio.gather(*[async_client.wait_for_task(x.task_uid) for x in tasks])
    yield
    if (
        "no_parallel" in request.keywords
        and "not no_parallel" not in request.keywords
        or "no_parallel" not in request.keywords
    ):
        indexes = await async_client.get_indexes()
        if indexes:
            tasks = await asyncio.gather(*[async_client.index(x.uid).delete() for x in indexes])
            await asyncio.gather(*[async_client.wait_for_task(x.task_uid) for x in tasks])


@pytest.fixture(scope="session")
def master_key():
    return MASTER_KEY


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture
async def async_indexes_sample(async_client):
    index_info = [
        {"uid": str(uuid4())},
        {"uid": str(uuid4()), "primary_key": "book_id"},
    ]
    indexes = []
    for index_args in index_info:
        index = await async_client.create_index(**index_args)
        indexes.append(index)
    yield indexes, index_info[0]["uid"], index_info[1]["uid"]


@pytest.fixture
def indexes_sample(client):
    index_info = [
        {"uid": str(uuid4())},
        {"uid": str(uuid4()), "primary_key": "book_id"},
    ]
    indexes = []
    for index_args in index_info:
        index = client.create_index(**index_args)
        indexes.append(index)
    yield indexes, index_info[0]["uid"], index_info[1]["uid"]


@pytest.fixture
def small_movies():
    with open(SMALL_MOVIES_PATH) as movie_file:
        yield json.loads(movie_file.read())


@pytest.fixture
def small_movies_csv_path(small_movies, tmp_path):
    file_path = tmp_path / "small_movies.csv"
    with open(file_path, "w") as f:
        field_names = list(small_movies[0].keys())
        writer = csv.DictWriter(f, fieldnames=field_names, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(small_movies)

    return file_path


@pytest.fixture
def small_movies_csv_path_semicolon_delimiter(small_movies, tmp_path):
    file_path = tmp_path / "small_movies.csv"
    with open(file_path, "w") as f:
        field_names = list(small_movies[0].keys())
        writer = csv.DictWriter(f, fieldnames=field_names, quoting=csv.QUOTE_MINIMAL, delimiter=";")
        writer.writeheader()
        writer.writerows(small_movies)

    return file_path


@pytest.fixture
def small_movies_ndjson_path(small_movies, tmp_path):
    file_path = tmp_path / "small_movies.ndjson"
    nd_json = [json.dumps(x) for x in small_movies]
    with open(file_path, "w") as f:
        for line in nd_json:
            f.write(f"{line}\n")

    return file_path


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


@pytest.fixture
async def async_index_with_documents(async_empty_index, small_movies):
    async def index_maker(documents=small_movies):
        index = await async_empty_index()
        response = await index.add_documents(documents)
        await async_wait_for_task(index.http_client, response.task_uid)
        return index

    return index_maker


@pytest.fixture
def index_with_documents(empty_index, small_movies):
    def index_maker(documents=small_movies):
        index = empty_index()
        response = index.add_documents(documents)
        wait_for_task(index.http_client, response.task_uid)
        return index

    return index_maker


@pytest.fixture
async def async_index_with_documents_and_vectors(async_empty_index, small_movies):
    small_movies[0]["_vectors"] = {"default": [0.1, 0.2]}
    for movie in small_movies[1:]:
        movie["_vectors"] = {"default": [0.9, 0.9]}

    async def index_maker(documents=small_movies):
        index = await async_empty_index()
        task = await index.update_embedders(
            Embedders(embedders={"default": UserProvidedEmbedder(dimensions=2)})
        )
        await async_wait_for_task(index.http_client, task.task_uid)

        response = await index.add_documents(documents)
        await async_wait_for_task(index.http_client, response.task_uid)
        return index

    return index_maker


@pytest.fixture
def index_with_documents_and_vectors(empty_index, small_movies):
    small_movies[0]["_vectors"] = {"default": [0.1, 0.2]}
    for movie in small_movies[1:]:
        movie["_vectors"] = {"default": [0.9, 0.9]}

    def index_maker(documents=small_movies):
        index = empty_index()
        task = index.update_embedders(
            Embedders(embedders={"default": UserProvidedEmbedder(dimensions=2)})
        )
        wait_for_task(index.http_client, task.task_uid)
        response = index.add_documents(documents)
        wait_for_task(index.http_client, response.task_uid)
        return index

    return index_maker


@pytest.fixture
async def default_search_key(async_client):
    keys = await async_client.get_keys()

    for key in keys.results:
        if key.actions == ["search"]:
            return key


@pytest.fixture(scope="session", autouse=True)
async def enable_vector_search():
    async with HttpxAsyncClient(
        base_url=BASE_URL, headers={"Authorization": f"Bearer {MASTER_KEY}"}
    ) as client:
        await client.patch("/experimental-features", json={"vectorStore": True})
        yield


@pytest.fixture
async def create_tasks(async_empty_index, small_movies):
    """Ensures there are some tasks present for testing."""
    index = await async_empty_index()
    await index.update_ranking_rules(["typo", "exactness"])
    await index.reset_ranking_rules()
    await index.add_documents(small_movies)
    await index.add_documents(small_movies)


@pytest.fixture
def new_settings():
    return MeilisearchSettings(
        ranking_rules=["typo", "words"],
        searchable_attributes=["title", "overview"],
        sortable_attributes=["genre", "title"],
        typo_tolerance=TypoTolerance(enabled=False),
        faceting=Faceting(max_values_per_facet=123),
        pagination=Pagination(max_total_hits=17),
        separator_tokens=["&sep", "/", "|"],
        non_separator_tokens=["#", "@"],
        search_cutoff_ms=100,
        dictionary=["S.O", "S.O.S"],
        # TODO: Add back after embedder setting issue fixed https://github.com/meilisearch/meilisearch/issues/4585
        # embedders={
        #     "default": UserProvidedEmbedder(dimensions=512),
        #     # "test1": HuggingFaceEmbedder(),
        #     "test2": OpenAiEmbedder(),
        #     # "test3": OllamaEmbedder(model="nomic-embed-text"),
        #     "test4": RestEmbedder(url="https://myurl.com"),
        # },
        proximity_precision=ProximityPrecision.BY_ATTRIBUTE,
    )
