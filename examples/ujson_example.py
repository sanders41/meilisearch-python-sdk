from __future__ import annotations

from pathlib import Path

from meilisearch_python_sdk import Client
from meilisearch_python_sdk.json_handler import UjsonHandler
from meilisearch_python_sdk.models.task import TaskInfo


def add_documents(file_path: Path | str = "../datasets/small_movies.json") -> TaskInfo:
    client = Client("http://127.0.0.1:7700", "masterKey", json_handler=UjsonHandler())
    index = client.create_index("movies", primary_key="id")
    return index.add_documents_from_file(file_path)


def main() -> int:
    add_documents()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
