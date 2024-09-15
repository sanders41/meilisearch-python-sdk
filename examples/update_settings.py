from __future__ import annotations

import json
from pathlib import Path

from meilisearch_python_sdk import Client, Index
from meilisearch_python_sdk.models.settings import MeilisearchSettings
from meilisearch_python_sdk.models.task import TaskInfo


def add_documents(
    index: Index, file_path: Path | str = "../datasets/small_movies.json"
) -> TaskInfo:
    with open(file_path) as f:
        documents = json.load(f)
    return index.add_documents(documents)


def update_settings(index: Index) -> TaskInfo:
    settings = MeilisearchSettings(
        filterable_attributes=["genre"], searchable_attributes=["title", "genre", "overview"]
    )

    return index.update_settings(settings)


def main() -> int:
    client = Client("http://127.0.0.1:7700", "masterKey")
    index = client.create_index("movies", primary_key="id")
    task = update_settings(index)
    client.wait_for_task(task.task_uid)
    add_documents(index)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
