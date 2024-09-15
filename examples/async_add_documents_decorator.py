from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aiofiles

from meilisearch_python_sdk import AsyncClient
from meilisearch_python_sdk.decorators import ConnectionInfo, async_add_documents


@async_add_documents(
    index_name="movies",
    connection_info=ConnectionInfo(url="http://127.0.0.1:7700", api_key="masterKey"),
)
async def load_documents(
    file_path: Path | str = "../datasets/small_movies.json",
) -> list[dict[str, Any]]:
    async with aiofiles.open(file_path) as f:
        data = await f.read()
        documents = json.loads(data)

    return documents


async def main() -> int:
    async with AsyncClient("http://127.0.0.1:7700", "masterKey") as client:
        index = await client.create_index("movies", "id")
        await load_documents()
        documents = await index.get_documents()

        print(documents)  # noqa: T201

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
