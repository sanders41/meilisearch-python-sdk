from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

import aiofiles

from meilisearch_python_sdk import AsyncClient, AsyncIndex
from meilisearch_python_sdk.models.search import SearchResults
from meilisearch_python_sdk.models.task import TaskInfo
from meilisearch_python_sdk.plugins import AsyncEvent, AsyncIndexPlugins
from meilisearch_python_sdk.types import JsonDict


class SearchTrackerPlugin:
    CONCURRENT_EVENT = True  # Specifies the plugin should be run concurrently with the search
    POST_EVENT = False
    PRE_EVENT = False

    def __init__(self, db_path: Path | str = "search_tracker.db") -> None:
        self.conn = sqlite3.Connection(db_path)
        self.create_table()

    def create_table(self) -> None:
        try:
            cursor = self.conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS searches(query STRING)")
        finally:
            cursor.close()

    async def run_plugin(self, event: AsyncEvent, **kwargs: Any) -> None:
        """Note that this example uses sqlite which does not provide an async driver.

        Typically if you are using the AsyncClient you would also be using an async driver for the
        database. sqlite is used in this example for simplicity.
        """
        if kwargs.get("query"):
            self.save_search_query(kwargs["query"])

    def save_search_query(self, query: str) -> None:
        try:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO searches VALUES(?)", (query,))
            self.conn.commit()
        finally:
            cursor.close()


async def add_documents(
    index: AsyncIndex, file_path: Path | str = "../datasets/small_movies.json"
) -> TaskInfo:
    async with aiofiles.open(file_path) as f:
        data = await f.read()
        documents = json.loads(data)
    return await index.add_documents(documents)


async def search(index: AsyncIndex, query: str) -> SearchResults[JsonDict]:
    return await index.search(query)


async def main() -> int:
    async with AsyncClient("http://127.0.0.1:7700", "masterKey") as client:
        plugins = AsyncIndexPlugins(search_plugins=(SearchTrackerPlugin(),))
        index = await client.create_index("movies", primary_key="id", plugins=plugins)
        task = await add_documents(index)
        await client.wait_for_task(task.task_uid)
        result = await index.search("Cars")
        print(result)  # noqa: T201

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
