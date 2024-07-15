import asyncio
import json

import aiofiles

from meilisearch_python_sdk import AsyncClient
from meilisearch_python_sdk.models.settings import MeilisearchSettings


async def main() -> int:
    async with aiofiles.open("../datasets/small_movies.json") as f:
        data = await f.read()
        documents = json.loads(data)

    async with AsyncClient("http://127.0.0.1:7700", "masterKey") as client:
        index = await client.create_index("movies", primary_key="id")
        settings = MeilisearchSettings(
            filterable_attributes=["genre"], searchable_attributes=["title", "genre", "overview"]
        )

        # Notice that the settings are updated before indexing the documents. Updating settings
        # after adding the documnts will cause the documents to be reindexed, which will be much
        # slower because the documents will have to be indexed twice.
        task = await index.update_settings(settings)
        await client.wait_for_task(task.task_uid)
        await index.add_documents(documents)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
