import asyncio
import csv
import json
import ssl
import sys
from logging import warning
from pathlib import Path
from uuid import uuid4

import pytest

try:
    import truststore as truststore
except ImportError:
    truststore = None

from httpx import AsyncClient as HttpxAsyncClient

from meilisearch_python_sdk import AsyncClient, Client
from meilisearch_python_sdk._task import async_wait_for_task, wait_for_task
from meilisearch_python_sdk.json_handler import OrjsonHandler, UjsonHandler
from meilisearch_python_sdk.models.settings import (
    Embedders,
    Faceting,
    LocalizedAttributes,
    MeilisearchSettings,
    Pagination,
    ProximityPrecision,
    TypoTolerance,
    UserProvidedEmbedder,
)

MASTER_KEY = "masterKey"

ROOT_PATH = Path().absolute()
SMALL_MOVIES_PATH = ROOT_PATH / "datasets" / "small_movies.json"


def pytest_addoption(parser):
    parser.addoption("--http2", action="store_true")


@pytest.fixture(scope="session")
def http2_enabled(request):
    return request.config.getoption("--http2")


@pytest.fixture(scope="session")
def ssl_verify(http2_enabled):
    if truststore:  # truststore is installed
        if http2_enabled:
            # http2 needs ssl so best to use truststore to make things work with mkcert
            return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT) if http2_enabled else True
        return True  # recommended default
    else:  # truststore isn't installed
        if sys.version_info >= (3, 10):  # should be available in 3.10+
            warning("truststore not installed, your environment may be broken run uv sync")
        # without truststore we can't verify the ssl (and when http2 is enabled, verification must be disabled)
        return not http2_enabled


@pytest.fixture(scope="session")
async def async_client(base_url, ssl_verify):
    async with AsyncClient(base_url, MASTER_KEY, verify=ssl_verify) as client:
        yield client


@pytest.fixture(scope="session")
async def async_client_orjson_handler(base_url, ssl_verify):
    async with AsyncClient(
        base_url, MASTER_KEY, json_handler=OrjsonHandler(), verify=ssl_verify
    ) as client:
        yield client


@pytest.fixture(scope="session")
async def async_client_ujson_handler(base_url, ssl_verify):
    async with AsyncClient(
        base_url, MASTER_KEY, json_handler=UjsonHandler(), verify=ssl_verify
    ) as client:
        yield client


@pytest.fixture(scope="session")
async def async_client_with_plugins(base_url, ssl_verify):
    async with AsyncClient(base_url, MASTER_KEY, verify=ssl_verify) as client:
        yield client


@pytest.fixture(scope="session")
def client(base_url, ssl_verify):
    yield Client(base_url, MASTER_KEY, verify=ssl_verify)


@pytest.fixture(scope="session")
def client_orjson_handler(base_url, ssl_verify):
    yield Client(base_url, MASTER_KEY, json_handler=OrjsonHandler(), verify=ssl_verify)


@pytest.fixture(scope="session")
def client_ujson_handler(base_url, ssl_verify):
    yield Client(base_url, MASTER_KEY, json_handler=UjsonHandler(), verify=ssl_verify)


@pytest.fixture(autouse=True)
async def clear_indexes(async_client, pytestconfig):
    """Auto-clears the indexes after each test function run if not a parallel test."""
    if "not no_parallel" != pytestconfig.getoption("-m"):
        indexes = await async_client.get_indexes()
        if indexes:
            tasks = await asyncio.gather(*[async_client.index(x.uid).delete() for x in indexes])
            await asyncio.gather(*[async_client.wait_for_task(x.task_uid) for x in tasks])
    yield
    if "not no_parallel" != pytestconfig.getoption("-m"):
        indexes = await async_client.get_indexes()
        if indexes:
            tasks = await asyncio.gather(*[async_client.index(x.uid).delete() for x in indexes])
            await asyncio.gather(*[async_client.wait_for_task(x.task_uid) for x in tasks])


@pytest.fixture(scope="session")
def master_key():
    return MASTER_KEY


@pytest.fixture(scope="session")
def base_url(http2_enabled):
    schema = "https" if http2_enabled else "http"
    return f"{schema}://127.0.0.1:7700"


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
async def enable_edit_by_function(base_url, ssl_verify):
    async with HttpxAsyncClient(
        base_url=base_url, headers={"Authorization": f"Bearer {MASTER_KEY}"}, verify=ssl_verify
    ) as client:
        await client.patch("/experimental-features", json={"editDocumentsByFunction": True})
    yield


@pytest.fixture(scope="session", autouse=True)
async def enable_network(base_url, ssl_verify):
    async with HttpxAsyncClient(
        base_url=base_url, headers={"Authorization": f"Bearer {MASTER_KEY}"}, verify=ssl_verify
    ) as client:
        await client.patch("/experimental-features", json={"network": True})
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
        proximity_precision=ProximityPrecision.BY_ATTRIBUTE,
        facet_search=False,
        prefix_search="disabled",
    )


@pytest.fixture
def new_settings_localized():
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
        proximity_precision=ProximityPrecision.BY_ATTRIBUTE,
        localized_attributes=[
            LocalizedAttributes(locales=["eng", "spa"], attribute_patterns=["*"]),
            LocalizedAttributes(locales=["ita"], attribute_patterns=["*_it"]),
        ],
    )
