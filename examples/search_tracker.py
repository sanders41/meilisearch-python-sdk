from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from meilisearch_python_sdk import Client, Index
from meilisearch_python_sdk.models.search import SearchResults
from meilisearch_python_sdk.models.task import TaskInfo
from meilisearch_python_sdk.plugins import Event, IndexPlugins
from meilisearch_python_sdk.types import JsonDict


class SearchTrackerPlugin:
    POST_EVENT = False
    PRE_EVENT = True  # Specifies the plugin should be run before the search

    def __init__(self, db_path: Path | str = "search_tracker.db") -> None:
        self.conn = sqlite3.Connection(db_path)
        self.create_table()

    def create_table(self) -> None:
        try:
            cursor = self.conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS searches(query STRING)")
        finally:
            cursor.close()

    def run_plugin(self, event: Event, **kwargs: Any) -> None:
        if kwargs.get("query"):
            self.save_search_query(kwargs["query"])

    def save_search_query(self, query: str) -> None:
        try:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO searches VALUES(?)", (query,))
            self.conn.commit()
        finally:
            cursor.close()


def add_documents(
    index: Index, file_path: Path | str = "../datasets/small_movies.json"
) -> TaskInfo:
    with open(file_path) as f:
        documents = json.load(f)
    return index.add_documents(documents)


def search(index: Index, query: str) -> SearchResults[JsonDict]:
    return index.search(query)


def main() -> int:
    client = Client("http://127.0.0.1:7700", "masterKey")
    plugins = IndexPlugins(search_plugins=(SearchTrackerPlugin(),))
    index = client.create_index("movies", primary_key="id", plugins=plugins)
    task = add_documents(index)
    client.wait_for_task(task.task_uid)
    result = search(index, "Cars")
    print(result)  # noqa: T201

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
