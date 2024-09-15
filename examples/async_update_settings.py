from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiofiles

from meilisearch_python_sdk import AsyncClient, AsyncIndex
from meilisearch_python_sdk.models.settings import MeilisearchSettings
from meilisearch_python_sdk.models.task import TaskInfo


async def add_documents(
    index: AsyncIndex, file_path: Path | str = "../datasets/small_movies.json"
) -> TaskInfo:
    async with aiofiles.open(file_path) as f:
        data = await f.read()
        documents = json.loads(data)

    return await index.add_documents(documents)


async def update_settings(index: AsyncIndex) -> TaskInfo:
    settings = MeilisearchSettings(
        filterable_attributes=["genre"], searchable_attributes=["title", "genre", "overview"]
    )

    return await index.update_settings(settings)


async def main() -> int:
    async with AsyncClient("http://127.0.0.1:7700", "masterKey") as client:
        index = await client.create_index("movies", primary_key="id")
        task = await update_settings(index)
        await client.wait_for_task(task.task_uid)
        await add_documents(index)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
