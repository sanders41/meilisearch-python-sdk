import csv
import json
from datetime import datetime
from math import ceil
from uuid import UUID, uuid4

import pytest

from meilisearch_python_sdk._task import wait_for_task
from meilisearch_python_sdk.errors import (
    InvalidDocumentError,
    MeilisearchApiError,
    MeilisearchError,
)
from meilisearch_python_sdk.index import _combine_documents, _load_documents_from_file
from meilisearch_python_sdk.json_handler import BuiltinHandler


class CustomEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (UUID, datetime)):
            return str(o)

        # Let the base class default method raise the TypeError
        return super().default(o)


def generate_test_movies(num_movies=50, id_start=0):
    movies = []
    # Each moves is ~ 174 bytes
    for i in range(num_movies):
        movie = {
            "id": i + id_start,
            "title": "test",
            "poster": "test",
            "overview": "test",
            "release_date": 1551830399,
            "pk_test": i + id_start + 1,
            "genre": "test",
        }
        movies.append(movie)

    return movies


def add_json_file(file_path, num_movies=50, id_start=0):
    with open(file_path, "w") as f:
        json.dump(generate_test_movies(num_movies, id_start), f)


def add_csv_file(file_path, num_movies=50, id_start=0):
    with open(file_path, "w") as f:
        movies = generate_test_movies(num_movies, id_start)
        field_names = list(movies[0].keys())
        writer = csv.DictWriter(f, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(movies)


def add_csv_file_semicolon_delimiter(file_path, num_movies=50, id_start=0):
    with open(file_path, "w") as f:
        movies = generate_test_movies(num_movies, id_start)
        field_names = list(movies[0].keys())
        writer = csv.DictWriter(f, fieldnames=field_names, delimiter=";")
        writer.writeheader()
        writer.writerows(movies)


def add_ndjson_file(file_path, num_movies=50, id_start=0):
    movies = [json.dumps(x) for x in generate_test_movies(num_movies, id_start)]
    with open(file_path, "w") as f:
        for line in movies:
            f.write(f"{line}\n")


@pytest.fixture
def add_document():
    return {
        "id": "1",
        "title": f"{'a' * 999999}",
        "poster": f"{'a' * 999999}",
        "overview": f"{'a' * 999999}",
        "release_date": 1551830399,
        "genre": f"{'a' * 999999}",
    }


def test_get_documents_default(empty_index):
    index = empty_index()
    response = index.get_documents()
    assert response.results == []


@pytest.mark.parametrize(
    "primary_key, expected_primary_key, compress",
    (("release_date", "release_date", True), (None, "id", False)),
)
def test_add_documents(primary_key, expected_primary_key, compress, empty_index, small_movies):
    index = empty_index()
    response = index.add_documents(small_movies, primary_key, compress=compress)
    update = wait_for_task(index.http_client, response.task_uid)
    assert index.get_primary_key() == expected_primary_key
    assert update.status == "succeeded"


@pytest.mark.parametrize("batch_size", (100, 500))
@pytest.mark.parametrize(
    "primary_key, expected_primary_key", (("release_date", "release_date"), (None, "id"))
)
@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_in_batches(
    batch_size, primary_key, expected_primary_key, compress, empty_index, small_movies
):
    index = empty_index()
    response = index.add_documents_in_batches(
        small_movies, batch_size=batch_size, primary_key=primary_key, compress=compress
    )
    assert ceil(len(small_movies) / batch_size) == len(response)

    tasks = [wait_for_task(index.http_client, x.task_uid) for x in response]
    assert {"succeeded"} == {x.status for x in tasks}
    assert index.get_primary_key() == expected_primary_key


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("combine_documents", (True, False))
@pytest.mark.parametrize(
    "number_of_files, documents_per_file, total_documents", ((1, 50, 50), (2, 50, 100))
)
@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_from_directory(
    path_type,
    combine_documents,
    number_of_files,
    documents_per_file,
    total_documents,
    compress,
    client,
    tmp_path,
):
    for i in range(number_of_files):
        add_json_file(tmp_path / f"test{i}.json", documents_per_file, i * documents_per_file)

    index = client.index(str(uuid4()))
    path = str(tmp_path) if path_type == "str" else tmp_path
    responses = index.add_documents_from_directory(
        path, combine_documents=combine_documents, compress=compress
    )
    [wait_for_task(index.http_client, x.task_uid) for x in responses]
    stats = index.get_stats()
    assert stats.number_of_documents == total_documents


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("combine_documents", (True, False))
@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_from_directory_csv_path(
    path_type, combine_documents, compress, client, tmp_path
):
    add_csv_file(tmp_path / "test1.csv", 10, 0)
    add_csv_file(tmp_path / "test2.csv", 10, 11)
    index = client.index(str(uuid4()))
    path = str(tmp_path) if path_type == "str" else tmp_path
    responses = index.add_documents_from_directory(
        path, combine_documents=combine_documents, document_type="csv", compress=compress
    )
    [wait_for_task(index.http_client, x.task_uid) for x in responses]
    stats = index.get_stats()
    assert stats.number_of_documents == 20


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("combine_documents", (True, False))
@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_from_directory_csv_path_with_delimiter(
    path_type, combine_documents, compress, client, tmp_path
):
    add_csv_file_semicolon_delimiter(tmp_path / "test1.csv", 10, 0)
    add_csv_file_semicolon_delimiter(tmp_path / "test2.csv", 10, 11)
    index = client.index(str(uuid4()))
    path = str(tmp_path) if path_type == "str" else tmp_path
    responses = index.add_documents_from_directory(
        path,
        combine_documents=combine_documents,
        document_type="csv",
        csv_delimiter=";",
        compress=compress,
    )
    [wait_for_task(index.http_client, x.task_uid) for x in responses]
    stats = index.get_stats()
    assert stats.number_of_documents == 20


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("combine_documents", (True, False))
@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_from_directory_ndjson(
    path_type, combine_documents, compress, client, tmp_path
):
    add_ndjson_file(tmp_path / "test1.ndjson", 10, 0)
    add_ndjson_file(tmp_path / "test2.ndjson", 10, 11)
    index = client.index(str(uuid4()))
    path = str(tmp_path) if path_type == "str" else tmp_path
    responses = index.add_documents_from_directory(
        path, combine_documents=combine_documents, document_type="ndjson", compress=compress
    )
    [wait_for_task(index.http_client, x.task_uid) for x in responses]
    stats = index.get_stats()
    assert stats.number_of_documents == 20


@pytest.mark.parametrize("combine_documents", (True, False))
@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_from_directory_no_documents(combine_documents, compress, client, tmp_path):
    with open(tmp_path / "test.txt", "w") as f:
        f.write("nothing")

    with pytest.raises(MeilisearchError):
        index = client.index(str(uuid4()))
        index.add_documents_from_directory(
            tmp_path, combine_documents=combine_documents, compress=compress
        )


@pytest.mark.parametrize("delimiter", (";;", "😀"))
def test_add_documents_from_directory_csv_delimiter_invalid(delimiter, client, tmp_path):
    add_csv_file(tmp_path / "test1.csv", 1, 0)
    index = client.index(str(uuid4()))
    with pytest.raises(ValueError):
        index.add_documents_from_directory(tmp_path, document_type="csv", csv_delimiter=delimiter)


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("combine_documents", (True, False))
@pytest.mark.parametrize(
    "batch_size, number_of_files, documents_per_file, total_documents",
    [(25, 1, 50, 50), (50, 2, 50, 100)],
)
@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_from_directory_in_batchs(
    path_type,
    combine_documents,
    batch_size,
    number_of_files,
    documents_per_file,
    total_documents,
    compress,
    client,
    tmp_path,
):
    for i in range(number_of_files):
        add_json_file(tmp_path / f"test{i}.json", documents_per_file, i * documents_per_file)

    index = client.index(str(uuid4()))
    path = str(tmp_path) if path_type == "str" else tmp_path
    responses = index.add_documents_from_directory_in_batches(
        path, batch_size=batch_size, combine_documents=combine_documents, compress=compress
    )

    [wait_for_task(index.http_client, x.task_uid) for x in responses]
    stats = index.get_stats()
    assert stats.number_of_documents == total_documents


@pytest.mark.parametrize("batch_size", (10, 25))
@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("combine_documents", (True, False))
@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_from_directory_in_batchs_csv(
    path_type, combine_documents, batch_size, compress, client, tmp_path
):
    add_csv_file(tmp_path / "test1.csv", 10, 0)
    add_csv_file(tmp_path / "test2.csv", 10, 11)
    index = client.index(str(uuid4()))
    path = str(tmp_path) if path_type == "str" else tmp_path
    responses = index.add_documents_from_directory_in_batches(
        path,
        batch_size=batch_size,
        combine_documents=combine_documents,
        document_type="csv",
        compress=compress,
    )

    [wait_for_task(index.http_client, x.task_uid) for x in responses]
    stats = index.get_stats()
    assert stats.number_of_documents == 20


@pytest.mark.parametrize("batch_size", (10, 25))
@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("combine_documents", (True, False))
@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_from_directory_in_batchs_ndjson(
    path_type, combine_documents, batch_size, compress, client, tmp_path
):
    add_ndjson_file(tmp_path / "test1.ndjson", 10, 0)
    add_ndjson_file(tmp_path / "test2.ndjson", 10, 11)
    index = client.index(str(uuid4()))
    path = str(tmp_path) if path_type == "str" else tmp_path
    responses = index.add_documents_from_directory_in_batches(
        path,
        batch_size=batch_size,
        combine_documents=combine_documents,
        document_type="ndjson",
        compress=compress,
    )

    [wait_for_task(index.http_client, x.task_uid) for x in responses]
    stats = index.get_stats()
    assert stats.number_of_documents == 20


@pytest.mark.parametrize(
    "primary_key, expected_primary_key", [("release_date", "release_date"), (None, "id")]
)
@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_from_file(
    path_type, primary_key, expected_primary_key, compress, client, small_movies_path
):
    index = client.index(str(uuid4()))
    path = str(small_movies_path) if path_type == "str" else small_movies_path
    response = index.add_documents_from_file(path, primary_key, compress=compress)

    update = wait_for_task(index.http_client, response.task_uid)
    assert index.get_primary_key() == expected_primary_key
    assert update.status == "succeeded"


def test_add_documents_from_file_orjson_handler(
    client_orjson_handler,
    small_movies_path,
):
    index = client_orjson_handler.index(str(uuid4()))
    response = index.add_documents_from_file(small_movies_path)

    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"


def test_add_documents_from_file_ujson_handler(
    client_ujson_handler,
    small_movies_path,
):
    index = client_ujson_handler.index(str(uuid4()))
    response = index.add_documents_from_file(small_movies_path)

    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"


@pytest.mark.parametrize(
    "primary_key, expected_primary_key", [("release_date", "release_date"), (None, "id")]
)
@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_from_file_csv(
    path_type, primary_key, expected_primary_key, compress, client, small_movies_csv_path
):
    index = client.index(str(uuid4()))
    path = str(small_movies_csv_path) if path_type == "str" else small_movies_csv_path
    response = index.add_documents_from_file(path, primary_key, compress=compress)

    update = wait_for_task(index.http_client, response.task_uid)
    assert index.get_primary_key() == expected_primary_key
    assert update.status == "succeeded"


@pytest.mark.parametrize(
    "primary_key, expected_primary_key", [("release_date", "release_date"), (None, "id")]
)
@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_raw_file_csv(
    path_type, primary_key, expected_primary_key, compress, client, small_movies_csv_path
):
    index = client.index(str(uuid4()))
    path = str(small_movies_csv_path) if path_type == "str" else small_movies_csv_path
    response = index.add_documents_from_raw_file(path, primary_key, compress=compress)
    update = wait_for_task(index.http_client, response.task_uid)
    assert index.get_primary_key() == expected_primary_key
    assert update.status == "succeeded"


@pytest.mark.parametrize(
    "primary_key, expected_primary_key", [("release_date", "release_date"), (None, "id")]
)
@pytest.mark.parametrize("compress", (True, False))
@pytest.mark.parametrize("path_type", ("path", "str"))
def test_add_documents_raw_file_csv_delimiter(
    path_type,
    primary_key,
    expected_primary_key,
    compress,
    client,
    small_movies_csv_path_semicolon_delimiter,
):
    index = client.index(str(uuid4()))
    path = (
        str(small_movies_csv_path_semicolon_delimiter)
        if path_type == "str"
        else small_movies_csv_path_semicolon_delimiter
    )
    response = index.add_documents_from_raw_file(
        path, primary_key, csv_delimiter=";", compress=compress
    )
    update = wait_for_task(index.http_client, response.task_uid)
    assert index.get_primary_key() == expected_primary_key
    assert update.status == "succeeded"


@pytest.mark.parametrize(
    "primary_key, expected_primary_key", [("release_date", "release_date"), (None, "id")]
)
@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_raw_file_ndjson(
    path_type, primary_key, expected_primary_key, compress, client, small_movies_ndjson_path
):
    index = client.index(str(uuid4()))
    path = str(small_movies_ndjson_path) if path_type == "str" else small_movies_ndjson_path
    response = index.add_documents_from_raw_file(path, primary_key, compress=compress)
    update = wait_for_task(index.http_client, response.task_uid)
    assert index.get_primary_key() == expected_primary_key
    assert update.status == "succeeded"


def test_add_documents_raw_file_not_found_error(client, tmp_path):
    with pytest.raises(MeilisearchError):
        index = client.index(str(uuid4()))
        index.add_documents_from_raw_file(tmp_path / "file.csv")


def test_add_document_raw_file_extension_error(client, tmp_path):
    file_path = tmp_path / "file.bad"
    with open(file_path, "w") as f:
        f.write("test")

    with pytest.raises(ValueError):
        index = client.index(str(uuid4()))
        index.add_documents_from_raw_file(file_path)


def test_add_documents_raw_file_csv_delimiter_non_csv_error(client, small_movies_ndjson_path):
    index = client.index(str(uuid4()))
    with pytest.raises(ValueError):
        index.add_documents_from_raw_file(small_movies_ndjson_path, csv_delimiter=";")


@pytest.mark.parametrize("delimiter", (";;", "😀"))
def test_add_documents_raw_file_csv_delimiter_invalid(delimiter, client, small_movies_csv_path):
    index = client.index(str(uuid4()))
    with pytest.raises(ValueError):
        index.add_documents_from_raw_file(small_movies_csv_path, csv_delimiter=delimiter)


@pytest.mark.parametrize(
    "primary_key, expected_primary_key", (("release_date", "release_date"), (None, "id"))
)
@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_from_file_ndjson(
    path_type, primary_key, expected_primary_key, compress, client, small_movies_ndjson_path
):
    index = client.index(str(uuid4()))
    path = str(small_movies_ndjson_path) if path_type == "str" else small_movies_ndjson_path
    response = index.add_documents_from_file(path, primary_key, compress=compress)

    update = wait_for_task(index.http_client, response.task_uid)
    assert index.get_primary_key() == expected_primary_key
    assert update.status == "succeeded"


def test_add_documents_from_file_invalid_extension(client):
    index = client.index(str(uuid4()))

    with pytest.raises(MeilisearchError):
        index.add_documents_from_file("test.bad")


@pytest.mark.parametrize("batch_size", (10, 25))
@pytest.mark.parametrize(
    "primary_key, expected_primary_key", (("release_date", "release_date"), (None, "id"))
)
@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_from_file_in_batches(
    path_type,
    batch_size,
    primary_key,
    expected_primary_key,
    compress,
    client,
    small_movies_path,
    small_movies,
):
    index = client.index(str(uuid4()))
    path = str(small_movies_path) if path_type == "str" else small_movies_path
    response = index.add_documents_from_file_in_batches(
        path, batch_size=batch_size, primary_key=primary_key, compress=compress
    )

    assert ceil(len(small_movies) / batch_size) == len(response)

    tasks = [wait_for_task(index.http_client, x.task_uid) for x in response]
    assert {"succeeded"} == {x.status for x in tasks}
    assert index.get_primary_key() == expected_primary_key


@pytest.mark.parametrize("batch_size", (100, 500))
@pytest.mark.parametrize(
    "primary_key, expected_primary_key", (("release_date", "release_date"), (None, "id"))
)
@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_from_file_in_batches_csv(
    path_type,
    batch_size,
    primary_key,
    expected_primary_key,
    compress,
    client,
    small_movies_csv_path,
    small_movies,
):
    index = client.index(str(uuid4()))
    path = str(small_movies_csv_path) if path_type == "str" else small_movies_csv_path
    response = index.add_documents_from_file_in_batches(
        path, batch_size=batch_size, primary_key=primary_key, compress=compress
    )

    assert ceil(len(small_movies) / batch_size) == len(response)

    tasks = [wait_for_task(index.http_client, x.task_uid) for x in response]
    assert {"succeeded"} == {x.status for x in tasks}
    assert index.get_primary_key() == expected_primary_key


@pytest.mark.parametrize("batch_size", (100, 500))
@pytest.mark.parametrize(
    "primary_key, expected_primary_key", [("release_date", "release_date"), (None, "id")]
)
@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_from_file_in_batches_csv_with_delimiter(
    path_type,
    batch_size,
    primary_key,
    expected_primary_key,
    compress,
    client,
    small_movies_csv_path_semicolon_delimiter,
    small_movies,
):
    index = client.index(str(uuid4()))
    path = (
        str(small_movies_csv_path_semicolon_delimiter)
        if path_type == "str"
        else small_movies_csv_path_semicolon_delimiter
    )
    response = index.add_documents_from_file_in_batches(
        path, batch_size=batch_size, primary_key=primary_key, csv_delimiter=";", compress=compress
    )

    assert ceil(len(small_movies) / batch_size) == len(response)

    tasks = [wait_for_task(index.http_client, x.task_uid) for x in response]
    assert {"succeeded"} == {x.status for x in tasks}
    assert index.get_primary_key() == expected_primary_key


@pytest.mark.parametrize("delimiter", (";;", "😀"))
def test_add_documents_from_file_in_batches_csv_with_delimiter_invalid(
    delimiter, client, small_movies_csv_path
):
    index = client.index(str(uuid4()))
    with pytest.raises(ValueError):
        index.add_documents_from_file_in_batches(small_movies_csv_path, csv_delimiter=delimiter)


@pytest.mark.parametrize("batch_size", (100, 500))
@pytest.mark.parametrize(
    "primary_key, expected_primary_key", [("release_date", "release_date"), (None, "id")]
)
@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_from_file_in_batches_ndjson(
    path_type,
    batch_size,
    primary_key,
    expected_primary_key,
    compress,
    client,
    small_movies_ndjson_path,
    small_movies,
):
    index = client.index(str(uuid4()))
    path = str(small_movies_ndjson_path) if path_type == "str" else small_movies_ndjson_path
    response = index.add_documents_from_file_in_batches(
        path, batch_size=batch_size, primary_key=primary_key, compress=compress
    )

    assert ceil(len(small_movies) / batch_size) == len(response)

    tasks = [wait_for_task(index.http_client, x.task_uid) for x in response]
    assert {"succeeded"} == {x.status for x in tasks}
    assert index.get_primary_key() == expected_primary_key


def test_add_documents_from_file_in_batches_invalid_extension(client):
    index = client.index(str(uuid4()))

    with pytest.raises(MeilisearchError):
        index.add_documents_from_file_in_batches("test.bad")


def test_get_document(index_with_documents):
    index = index_with_documents()
    response = index.get_document("500682")
    assert response["title"] == "The Highwaymen"


def test_get_document_inexistent(empty_index):
    with pytest.raises(MeilisearchApiError):
        index = empty_index()
        index.get_document("123")


def test_get_document_with_fields(index_with_documents):
    index = index_with_documents()
    response = index.get_document("500682", fields=["title", "overview"])
    assert len(response.keys()) == 2
    assert "title" in response.keys()
    assert "overview" in response.keys()


def test_get_document_with_vectors(index_with_documents):
    index = index_with_documents()
    response = index.get_document("500682", retrieve_vectors=True)
    assert "_vectors" in response.keys()


def test_get_documents_populated(index_with_documents):
    index = index_with_documents()
    response = index.get_documents()
    assert len(response.results) == 20


def test_get_documents_offset_optional_params(index_with_documents):
    index = index_with_documents()
    response = index.get_documents()
    assert len(response.results) == 20
    response_offset_limit = index.get_documents(limit=3, offset=1, fields=["title", "overview"])
    assert len(response_offset_limit.results) == 3
    assert response_offset_limit.results[0]["title"] == response.results[1]["title"]
    assert response_offset_limit.results[0]["overview"] == response.results[1]["overview"]


def test_get_documents_filter(index_with_documents):
    index = index_with_documents()
    response = index.update_filterable_attributes(["genre"])
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_documents(filter="genre=action")
    genres = set([x["genre"] for x in response.results])
    assert len(genres) == 1
    assert next(iter(genres)) == "action"


def test_get_documents_with_vectors(index_with_documents):
    index = index_with_documents()
    response = index.update_filterable_attributes(["genre"])
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_documents(retrieve_vectors=True)
    assert all("_vectors" in x.keys() for x in response.results)


def test_get_documents_filter_with_fields(index_with_documents):
    index = index_with_documents()
    response = index.update_filterable_attributes(["genre"])
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_documents(fields=["genre"], filter="genre=action")
    genres = set([x["genre"] for x in response.results])
    assert len(genres) == 1
    assert next(iter(genres)) == "action"


@pytest.mark.parametrize("compress", (True, False))
def test_update_documents(compress, index_with_documents, small_movies):
    index = index_with_documents()
    response = index.get_documents()
    doc_id = response.results[0]["id"]
    response.results[0]["title"] = "Some title"
    update = index.update_documents([response.results[0]], compress=compress)
    wait_for_task(index.http_client, update.task_uid)
    response = index.get_document(doc_id)
    assert response["title"] == "Some title"
    update = index.update_documents(small_movies)
    wait_for_task(index.http_client, update.task_uid)
    response = index.get_document(doc_id)
    assert response["title"] != "Some title"


@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_with_primary_key(compress, client, small_movies):
    primary_key = "release_date"
    index = client.index(str(uuid4()))
    update = index.update_documents(small_movies, primary_key=primary_key, compress=compress)
    wait_for_task(index.http_client, update.task_uid)
    assert index.get_primary_key() == primary_key


@pytest.mark.parametrize("batch_size, compress", ((100, True), (500, False)))
def test_update_documents_in_batches(batch_size, compress, index_with_documents, small_movies):
    index = index_with_documents()
    response = index.get_documents()
    doc_id = response.results[0]["id"]
    response.results[0]["title"] = "Some title"
    update = index.update_documents([response.results[0]], compress=compress)
    wait_for_task(index.http_client, update.task_uid)

    response = index.get_document(doc_id)
    assert response["title"] == "Some title"
    updates = index.update_documents_in_batches(
        small_movies, batch_size=batch_size, compress=compress
    )
    assert ceil(len(small_movies) / batch_size) == len(updates)

    [wait_for_task(index.http_client, x.task_uid) for x in updates]

    response = index.get_document(doc_id)
    assert response["title"] != "Some title"


@pytest.mark.parametrize("batch_size, compress", ((100, False), (500, True)))
def test_update_documents_in_batches_with_primary_key(batch_size, compress, client, small_movies):
    primary_key = "release_date"
    index = client.index(str(uuid4()))
    updates = index.update_documents_in_batches(
        small_movies, batch_size=batch_size, primary_key=primary_key, compress=compress
    )
    assert ceil(len(small_movies) / batch_size) == len(updates)

    tasks = [wait_for_task(index.http_client, x.task_uid) for x in updates]
    assert {"succeeded"} == {x.status for x in tasks}
    assert index.get_primary_key() == primary_key


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("combine_documents", (True, False))
@pytest.mark.parametrize(
    "number_of_files, documents_per_file, total_documents", [(1, 50, 50), (10, 50, 500)]
)
@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_from_directory(
    path_type,
    combine_documents,
    number_of_files,
    documents_per_file,
    total_documents,
    compress,
    client,
    tmp_path,
):
    for i in range(number_of_files):
        add_json_file(tmp_path / f"test{i}.json", documents_per_file, i * documents_per_file)

    index = client.index(str(uuid4()))
    path = str(tmp_path) if path_type == "str" else tmp_path
    responses = index.update_documents_from_directory(
        path, combine_documents=combine_documents, compress=compress
    )
    [wait_for_task(index.http_client, x.task_uid) for x in responses]
    stats = index.get_stats()
    assert stats.number_of_documents == total_documents


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("combine_documents", (True, False))
@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_from_directory_csv(
    path_type, combine_documents, compress, client, tmp_path
):
    add_csv_file(tmp_path / "test1.csv", 10, 0)
    add_csv_file(tmp_path / "test2.csv", 10, 11)
    index = client.index(str(uuid4()))
    path = str(tmp_path) if path_type == "str" else tmp_path
    responses = index.update_documents_from_directory(
        path, combine_documents=combine_documents, document_type="csv", compress=compress
    )
    [wait_for_task(index.http_client, x.task_uid) for x in responses]
    stats = index.get_stats()
    assert stats.number_of_documents == 20


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("combine_documents", (True, False))
@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_from_directory_csv_with_delimiter(
    path_type, combine_documents, compress, client, tmp_path
):
    add_csv_file_semicolon_delimiter(tmp_path / "test1.csv", 10, 0)
    add_csv_file_semicolon_delimiter(tmp_path / "test2.csv", 10, 11)
    index = client.index(str(uuid4()))
    path = str(tmp_path) if path_type == "str" else tmp_path
    responses = index.update_documents_from_directory(
        path,
        combine_documents=combine_documents,
        document_type="csv",
        csv_delimiter=";",
        compress=compress,
    )
    [wait_for_task(index.http_client, x.task_uid) for x in responses]
    stats = index.get_stats()
    assert stats.number_of_documents == 20


@pytest.mark.parametrize("delimiter", (";;", "😀"))
def test_update_documents_from_directory_csv_delimiter_invalid(delimiter, client, tmp_path):
    add_csv_file_semicolon_delimiter(tmp_path / "test1.csv", 1, 0)
    index = client.index(str(uuid4()))
    with pytest.raises(ValueError):
        index.update_documents_from_directory(
            tmp_path, document_type="csv", csv_delimiter=delimiter
        )


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("combine_documents", (True, False))
@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_from_directory_ndjson(
    path_type, combine_documents, compress, client, tmp_path
):
    add_ndjson_file(tmp_path / "test1.ndjson", 10, 0)
    add_ndjson_file(tmp_path / "test2.ndjson", 10, 11)
    index = client.index(str(uuid4()))
    path = str(tmp_path) if path_type == "str" else tmp_path
    responses = index.update_documents_from_directory(
        path, combine_documents=combine_documents, document_type="ndjson", compress=compress
    )
    [wait_for_task(index.http_client, x.task_uid) for x in responses]
    stats = index.get_stats()
    assert stats.number_of_documents == 20


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("combine_documents", (True, False))
@pytest.mark.parametrize(
    "batch_size, number_of_files, documents_per_file, total_documents",
    [(25, 1, 50, 50), (50, 2, 50, 100)],
)
@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_from_directory_in_batchs(
    path_type,
    combine_documents,
    batch_size,
    number_of_files,
    documents_per_file,
    total_documents,
    compress,
    client,
    tmp_path,
):
    for i in range(number_of_files):
        add_json_file(tmp_path / f"text{i}.json", documents_per_file, i * documents_per_file)

    index = client.index(str(uuid4()))
    path = str(tmp_path) if path_type == "str" else tmp_path
    responses = index.update_documents_from_directory_in_batches(
        path, batch_size=batch_size, combine_documents=combine_documents, compress=compress
    )

    [wait_for_task(index.http_client, x.task_uid) for x in responses]
    stats = index.get_stats()
    assert stats.number_of_documents == total_documents


@pytest.mark.parametrize("batch_size", (100, 500))
@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("combine_documents", (True, False))
@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_from_directory_in_batchs_csv(
    path_type, combine_documents, batch_size, compress, client, tmp_path
):
    add_csv_file(tmp_path / "test1.csv", 10, 0)
    add_csv_file(tmp_path / "test2.csv", 10, 11)
    index = client.index(str(uuid4()))
    path = str(tmp_path) if path_type == "str" else tmp_path
    responses = index.update_documents_from_directory_in_batches(
        path,
        batch_size=batch_size,
        combine_documents=combine_documents,
        document_type="csv",
        compress=compress,
    )

    [wait_for_task(index.http_client, x.task_uid) for x in responses]
    stats = index.get_stats()
    assert stats.number_of_documents == 20


@pytest.mark.parametrize("batch_size", (100, 500))
@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("combine_documents", (True, False))
@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_from_directory_in_batchs_csv_delimiter(
    path_type, combine_documents, batch_size, compress, client, tmp_path
):
    add_csv_file_semicolon_delimiter(tmp_path / "test1.csv", 10, 0)
    add_csv_file_semicolon_delimiter(tmp_path / "test2.csv", 10, 11)
    index = client.index(str(uuid4()))
    path = str(tmp_path) if path_type == "str" else tmp_path
    responses = index.update_documents_from_directory_in_batches(
        path,
        batch_size=batch_size,
        combine_documents=combine_documents,
        document_type="csv",
        csv_delimiter=";",
        compress=compress,
    )

    [wait_for_task(index.http_client, x.task_uid) for x in responses]
    stats = index.get_stats()
    assert stats.number_of_documents == 20


@pytest.mark.parametrize("delimiter", (";;", "😀"))
def test_update_documents_from_directory_in_batches_csv_delimiter_invalid(
    delimiter, client, tmp_path
):
    add_csv_file_semicolon_delimiter(tmp_path / "test1.csv", 1, 0)
    index = client.index(str(uuid4()))
    with pytest.raises(ValueError):
        index.update_documents_from_directory_in_batches(
            tmp_path, document_type="csv", csv_delimiter=delimiter
        )


@pytest.mark.parametrize("batch_size", (100, 500))
@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("combine_documents", (True, False))
@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_from_directory_in_batchs_ndjson(
    path_type, combine_documents, batch_size, compress, client, tmp_path
):
    add_ndjson_file(tmp_path / "test1.ndjson", 10, 0)
    add_ndjson_file(tmp_path / "test2.ndjson", 10, 11)
    index = client.index(str(uuid4()))
    path = str(tmp_path) if path_type == "str" else tmp_path
    responses = index.update_documents_from_directory_in_batches(
        path,
        batch_size=batch_size,
        combine_documents=combine_documents,
        document_type="ndjson",
        compress=compress,
    )

    [wait_for_task(index.http_client, x.task_uid) for x in responses]
    stats = index.get_stats()
    assert stats.number_of_documents == 20


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_from_file(path_type, compress, client, small_movies, small_movies_path):
    small_movies[0]["title"] = "Some title"
    movie_id = small_movies[0]["id"]
    index = client.index(str(uuid4()))
    response = index.add_documents(small_movies, compress=compress)
    update = wait_for_task(index.http_client, response.task_uid)
    assert index.get_primary_key() == "id"
    response = index.get_documents()
    got_title = filter(lambda x: x["id"] == movie_id, response.results)
    assert list(got_title)[0]["title"] == "Some title"
    path = str(small_movies_path) if path_type == "str" else small_movies_path
    update = index.update_documents_from_file(path, compress=compress)
    update = wait_for_task(index.http_client, update.task_uid)  # type: ignore
    assert update.status == "succeeded"
    response = index.get_documents()
    assert response.results[0]["title"] != "Some title"


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_from_file_csv(
    path_type, compress, client, small_movies, small_movies_csv_path
):
    small_movies[0]["title"] = "Some title"
    movie_id = small_movies[0]["id"]
    index = client.index(str(uuid4()))
    response = index.add_documents(small_movies, compress=compress)
    update = wait_for_task(index.http_client, response.task_uid)
    assert index.get_primary_key() == "id"
    response = index.get_documents()
    got_title = filter(lambda x: x["id"] == movie_id, response.results)
    assert list(got_title)[0]["title"] == "Some title"
    path = str(small_movies_csv_path) if path_type == "str" else small_movies_csv_path
    update = index.update_documents_from_file(path, compress=compress)
    update = wait_for_task(index.http_client, update.task_uid)  # type: ignore
    assert update.status == "succeeded"
    response = index.get_documents()
    assert response.results[0]["title"] != "Some title"


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_from_file_csv_with_delimiter(
    path_type, compress, client, small_movies, small_movies_csv_path_semicolon_delimiter
):
    small_movies[0]["title"] = "Some title"
    movie_id = small_movies[0]["id"]
    index = client.index(str(uuid4()))
    response = index.add_documents(small_movies, compress=compress)
    update = wait_for_task(index.http_client, response.task_uid)
    assert index.get_primary_key() == "id"
    response = index.get_documents()
    got_title = filter(lambda x: x["id"] == movie_id, response.results)
    assert list(got_title)[0]["title"] == "Some title"
    path = (
        str(small_movies_csv_path_semicolon_delimiter)
        if path_type == "str"
        else small_movies_csv_path_semicolon_delimiter
    )
    update = index.update_documents_from_file(path, csv_delimiter=";", compress=compress)
    update = wait_for_task(index.http_client, update.task_uid)  # type: ignore
    assert update.status == "succeeded"
    response = index.get_documents()
    assert response.results[0]["title"] != "Some title"


@pytest.mark.parametrize("delimiter", (";;", "😀"))
def test_update_documents_from_file_csv_delimiter_invalid(
    delimiter, client, small_movies_csv_path_semicolon_delimiter
):
    index = client.index(str(uuid4()))
    with pytest.raises(ValueError):
        index.update_documents_from_file(
            small_movies_csv_path_semicolon_delimiter, csv_delimiter=delimiter
        )


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_from_file_ndjson(
    path_type, compress, client, small_movies, small_movies_ndjson_path
):
    small_movies[0]["title"] = "Some title"
    movie_id = small_movies[0]["id"]
    index = client.index(str(uuid4()))
    response = index.add_documents(small_movies, compress=compress)
    update = wait_for_task(index.http_client, response.task_uid)
    assert index.get_primary_key() == "id"
    response = index.get_documents()
    got_title = filter(lambda x: x["id"] == movie_id, response.results)
    assert list(got_title)[0]["title"] == "Some title"
    path = str(small_movies_ndjson_path) if path_type == "str" else small_movies_ndjson_path
    update = index.update_documents_from_file(path, compress=compress)
    update = wait_for_task(index.http_client, update.task_uid)  # type: ignore
    assert update.status == "succeeded"
    response = index.get_documents()
    assert response.results[0]["title"] != "Some title"


@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_from_file_with_primary_key(compress, client, small_movies_path):
    primary_key = "release_date"
    index = client.index(str(uuid4()))
    update = index.update_documents_from_file(
        small_movies_path, primary_key=primary_key, compress=compress
    )
    wait_for_task(index.http_client, update.task_uid)
    assert index.get_primary_key() == primary_key


def test_update_documents_from_file_invalid_extension(client):
    index = client.index(str(uuid4()))

    with pytest.raises(MeilisearchError):
        index.update_documents_from_file("test.bad")


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("batch_size", (100, 500))
@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_from_file_in_batches(
    path_type, batch_size, compress, client, small_movies_path, small_movies
):
    small_movies[0]["title"] = "Some title"
    movie_id = small_movies[0]["id"]
    index = client.index(str(uuid4()))
    response = index.add_documents(small_movies, compress=compress)
    wait_for_task(index.http_client, response.task_uid)
    assert index.get_primary_key() == "id"
    response = index.get_documents()
    got_title = filter(lambda x: x["id"] == movie_id, response.results)
    assert list(got_title)[0]["title"] == "Some title"
    path = str(small_movies_path) if path_type == "str" else small_movies_path
    updates = index.update_documents_from_file_in_batches(
        path, batch_size=batch_size, compress=compress
    )
    assert ceil(len(small_movies) / batch_size) == len(updates)

    tasks = [wait_for_task(index.http_client, x.task_uid) for x in updates]
    assert {"succeeded"} == {x.status for x in tasks}

    response = index.get_documents()
    assert response.results[0]["title"] != "Some title"


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("batch_size", (100, 500))
@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_from_file_in_batches_csv(
    path_type, batch_size, compress, client, small_movies_csv_path, small_movies
):
    small_movies[0]["title"] = "Some title"
    movie_id = small_movies[0]["id"]
    index = client.index(str(uuid4()))
    response = index.add_documents(small_movies, compress=compress)
    wait_for_task(index.http_client, response.task_uid)
    assert index.get_primary_key() == "id"
    response = index.get_documents()
    got_title = filter(lambda x: x["id"] == movie_id, response.results)
    assert list(got_title)[0]["title"] == "Some title"
    path = str(small_movies_csv_path) if path_type == "str" else small_movies_csv_path
    updates = index.update_documents_from_file_in_batches(
        path, batch_size=batch_size, compress=compress
    )
    assert ceil(len(small_movies) / batch_size) == len(updates)

    tasks = [wait_for_task(index.http_client, x.task_uid) for x in updates]
    assert {"succeeded"} == {x.status for x in tasks}

    response = index.get_documents()
    assert response.results[0]["title"] != "Some title"


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("batch_size", (100, 500))
@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_from_file_in_batches_ndjson(
    path_type, batch_size, compress, client, small_movies_ndjson_path, small_movies
):
    small_movies[0]["title"] = "Some title"
    movie_id = small_movies[0]["id"]
    index = client.index(str(uuid4()))
    response = index.add_documents(small_movies, compress=compress)
    wait_for_task(index.http_client, response.task_uid)
    assert index.get_primary_key() == "id"
    response = index.get_documents()
    got_title = filter(lambda x: x["id"] == movie_id, response.results)
    assert list(got_title)[0]["title"] == "Some title"
    path = str(small_movies_ndjson_path) if path_type == "str" else small_movies_ndjson_path
    updates = index.update_documents_from_file_in_batches(
        path, batch_size=batch_size, compress=compress
    )
    assert ceil(len(small_movies) / batch_size) == len(updates)

    tasks = [wait_for_task(index.http_client, x.task_uid) for x in updates]
    assert {"succeeded"} == {x.status for x in tasks}

    response = index.get_documents()
    assert response.results[0]["title"] != "Some title"


def test_update_documents_from_file_in_batches_invalid_extension(client):
    index = client.index(str(uuid4()))

    with pytest.raises(MeilisearchError):
        index.update_documents_from_file_in_batches("test.bad")


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_raw_file_csv(
    path_type, compress, client, small_movies_csv_path, small_movies
):
    small_movies[0]["title"] = "Some title"
    movie_id = small_movies[0]["id"]
    index = client.index(str(uuid4()))
    response = index.add_documents(small_movies, compress=compress)
    update = wait_for_task(index.http_client, response.task_uid)
    assert index.get_primary_key() == "id"
    response = index.get_documents()
    got_title = filter(lambda x: x["id"] == movie_id, response.results)
    assert list(got_title)[0]["title"] == "Some title"
    path = str(small_movies_csv_path) if path_type == "str" else small_movies_csv_path
    update = index.update_documents_from_raw_file(path, primary_key="id", compress=compress)
    update = wait_for_task(index.http_client, update.task_uid)  # type: ignore
    assert update.status == "succeeded"
    response = index.get_documents()
    assert response.results[0]["title"] != "Some title"


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_raw_file_csv_with_delimiter(
    path_type, compress, client, small_movies_csv_path_semicolon_delimiter, small_movies
):
    small_movies[0]["title"] = "Some title"
    movie_id = small_movies[0]["id"]
    index = client.index(str(uuid4()))
    response = index.add_documents(small_movies, compress=compress)
    update = wait_for_task(index.http_client, response.task_uid)
    assert index.get_primary_key() == "id"
    response = index.get_documents()
    got_title = filter(lambda x: x["id"] == movie_id, response.results)
    assert list(got_title)[0]["title"] == "Some title"
    path = (
        str(small_movies_csv_path_semicolon_delimiter)
        if path_type == "str"
        else small_movies_csv_path_semicolon_delimiter
    )
    update = index.update_documents_from_raw_file(
        path, primary_key="id", csv_delimiter=";", compress=compress
    )
    update = wait_for_task(index.http_client, update.task_uid)  # type: ignore
    assert update.status == "succeeded"
    response = index.get_documents()
    assert response.results[0]["title"] != "Some title"


def test_update_documents_from_raw_file_csv_delimiter_non_csv(client, small_movies_ndjson_path):
    index = client.index(str(uuid4()))
    with pytest.raises(ValueError):
        index.update_documents_from_raw_file(small_movies_ndjson_path, csv_delimiter=";")


@pytest.mark.parametrize("delimiter", (";;", "😀"))
def test_update_documents_from_raw_file_csv_delimiter_invalid(
    delimiter, client, small_movies_csv_path_semicolon_delimiter
):
    index = client.index(str(uuid4()))
    with pytest.raises(ValueError):
        index.update_documents_from_raw_file(
            small_movies_csv_path_semicolon_delimiter, csv_delimiter=delimiter
        )


@pytest.mark.parametrize("path_type", ("path", "str"))
@pytest.mark.parametrize("compress", (True, False))
def test_update_documents_raw_file_ndjson(
    path_type, compress, client, small_movies_ndjson_path, small_movies
):
    small_movies[0]["title"] = "Some title"
    movie_id = small_movies[0]["id"]
    index = client.index(str(uuid4()))
    response = index.add_documents(small_movies, compress=compress)
    update = wait_for_task(index.http_client, response.task_uid)
    assert index.get_primary_key() == "id"
    response = index.get_documents()
    got_title = filter(lambda x: x["id"] == movie_id, response.results)
    assert list(got_title)[0]["title"] == "Some title"
    path = str(small_movies_ndjson_path) if path_type == "str" else small_movies_ndjson_path
    update = index.update_documents_from_raw_file(path, compress=compress)
    update = wait_for_task(index.http_client, update.task_uid)  # type: ignore
    assert update.status == "succeeded"
    response = index.get_documents()
    assert response.results[0]["title"] != "Some title"


def test_update_documents_raw_file_not_found_error(client, tmp_path):
    with pytest.raises(MeilisearchError):
        index = client.index(str(uuid4()))
        index.update_documents_from_raw_file(tmp_path / "file.csv")


def test_update_document_raw_file_extension_error(client, tmp_path):
    file_path = tmp_path / "file.bad"
    with open(file_path, "w") as f:
        f.write("test")

    with pytest.raises(ValueError):
        index = client.index(str(uuid4()))
        index.update_documents_from_raw_file(file_path)


def test_delete_document(index_with_documents):
    index = index_with_documents()
    response = index.delete_document("500682")
    wait_for_task(index.http_client, response.task_uid)
    with pytest.raises(MeilisearchApiError):
        index.get_document("500682")


def test_delete_documents(index_with_documents):
    to_delete = ["522681", "450465", "329996"]
    index = index_with_documents()
    response = index.delete_documents(to_delete)
    wait_for_task(index.http_client, response.task_uid)
    documents = index.get_documents()
    ids = [x["id"] for x in documents.results]
    assert to_delete not in ids


def test_delete_documents_by_filter(index_with_documents):
    index = index_with_documents()
    response = index.update_filterable_attributes(["genre"])
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_documents()
    assert "action" in ([x.get("genre") for x in response.results])
    response = index.delete_documents_by_filter("genre=action")
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_documents()
    genres = [x.get("genre") for x in response.results]
    assert "action" not in genres
    assert "cartoon" in genres


def test_delete_documents_in_batches_by_filter(index_with_documents):
    index = index_with_documents()
    response = index.update_filterable_attributes(["genre", "release_date"])
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_documents()
    assert "action" in [x.get("genre") for x in response.results]
    assert 1520035200 in [x.get("release_date") for x in response.results]
    response = index.delete_documents_in_batches_by_filter(
        ["genre=action", "release_date=1520035200"]
    )
    for task in response:
        wait_for_task(index.http_client, task.task_uid)
    response = index.get_documents()
    genres = [x.get("genre") for x in response.results]
    release_dates = [x.get("release_date") for x in response.results]
    assert "action" not in genres
    assert "cartoon" in genres
    assert len(release_dates) > 0
    assert 1520035200 not in release_dates


def test_delete_all_documents(index_with_documents):
    index = index_with_documents()
    response = index.delete_all_documents()
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_documents()
    assert response.results == []


def test_load_documents_from_file_invalid_document(tmp_path):
    doc = {"id": 1, "name": "test"}
    file_path = tmp_path / "test.json"
    with open(file_path, "w") as f:
        json.dump(doc, f)

    with pytest.raises(InvalidDocumentError):
        _load_documents_from_file(file_path, json_handler=BuiltinHandler())


def test_combine_documents():
    docs = [
        [{"id": 1, "name": "Test 1"}, {"id": 2, "name": "Test 2"}],
        [{"id": 3, "name": "Test 3"}],
    ]

    combined = _combine_documents(docs)

    assert len(combined) == 3
    assert [1, 2, 3] == [x["id"] for x in combined]


@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_custom_serializer(compress, empty_index):
    documents = [
        {"id": uuid4(), "title": "test 1", "when": datetime.now()},
        {"id": uuid4(), "title": "Test 2", "when": datetime.now()},
    ]
    index = empty_index()
    index._json_handler = BuiltinHandler(serializer=CustomEncoder)
    response = index.add_documents(documents, compress=compress)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"


@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_orjson_handler(compress, client_orjson_handler, small_movies):
    index = client_orjson_handler.create_index(str(uuid4()))
    response = index.add_documents(small_movies, compress=compress)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"


@pytest.mark.parametrize("compress", (True, False))
def test_add_documents_ujson_handler(compress, client_ujson_handler, small_movies):
    index = client_ujson_handler.create_index(str(uuid4()))
    response = index.add_documents(small_movies, compress=compress)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"


def test_edit_documents_by_function(index_with_documents):
    index = index_with_documents()
    task = index.update_filterable_attributes(["id"])
    wait_for_task(index.http_client, task.task_uid)
    response = index.edit_documents(
        function="if doc.id == context.docid {doc.title = `${doc.title.to_upper()}`}",
        context={"docid": "299537"},
        filter='id = "299537" OR id = "287947"',
    )
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_document("299537")

    assert response["title"] == "CAPTAIN MARVEL"

    response = index.get_document("287947")

    assert response["title"] == "Shazam!"
