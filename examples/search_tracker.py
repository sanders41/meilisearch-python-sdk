import json
import sqlite3
from typing import Any

from meilisearch_python_sdk import Client
from meilisearch_python_sdk.plugins import Event, IndexPlugins


class SearchTrackerPlugin:
    POST_EVENT = False
    PRE_EVENT = True  # Specifies the plugin should be run before the search

    def __init__(self) -> None:
        self.conn = sqlite3.Connection("search_tracker.db")
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


def main() -> int:
    with open("../datasets/small_movies.json") as f:
        documents = json.load(f)

    client = Client("http://127.0.0.1:7700", "masterKey")
    plugins = IndexPlugins(search_plugins=(SearchTrackerPlugin(),))
    index = client.create_index("movies", primary_key="id", plugins=plugins)
    task = index.add_documents(documents)
    client.wait_for_task(task.task_uid)
    result = index.search("Cars")
    print(result)  # noqa: T201

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
