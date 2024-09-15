from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiofiles

from meilisearch_python_sdk import AsyncClient, AsyncIndex
from meilisearch_python_sdk.models.task import TaskInfo


async def add_documents_in_batches(
    index: AsyncIndex, file_path: Path | str = "../datasets/small_movies.json"
) -> list[TaskInfo]:
    async with aiofiles.open(file_path) as f:
        data = await f.read()
        documents = json.loads(data)

    # Meilisearch prefers larger batch sizes so set this as large as you can.
    return await index.add_documents_in_batches(documents, primary_key="id", batch_size=1000)


async def main() -> int:
    async with AsyncClient("http://127.0.0.1:7700", "masterKey") as client:
        index = await client.create_index("movies", primary_key="id")

        await add_documents_in_batches(index)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
