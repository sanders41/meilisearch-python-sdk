from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from typing import Any

import aiofiles

from meilisearch_python_sdk import AsyncClient
from meilisearch_python_sdk.models.search import SearchResults
from meilisearch_python_sdk.plugins import AsyncEvent, AsyncIndexPlugins
from meilisearch_python_sdk.types import JsonMapping


class ModifyDocumentPlugin:
    CONCURRENT_EVENT = False
    POST_EVENT = False
    PRE_EVENT = True  # Specifies the plugin should be run before adding documents

    async def run_document_plugin(
        self, event: AsyncEvent, *, documents: Sequence[JsonMapping], **kwargs: Any
    ) -> Sequence[JsonMapping]:
        updated = []
        for i, document in enumerate(documents):
            if i % 2 == 0:
                document["access"] = "admin"
            else:
                document["access"] = "read"

            updated.append(document)

        return updated


class FilterSearchResultsPlugin:
    CONCURRENT_EVENT = False
    POST_EVENT = True  # Specifies the plugin should be run after the search
    PRE_EVENT = False

    async def run_post_search_plugin(
        self, event: AsyncEvent, *, search_results: SearchResults, **kwargs: Any
    ) -> SearchResults:
        filtered_hits = []
        for hit in search_results.hits:
            if hit["access"] != "admin":
                filtered_hits.append(hit)

        search_results.hits = filtered_hits

        return search_results


async def main() -> int:
    async with aiofiles.open("../datasets/small_movies.json") as f:
        data = await f.read()
        documents = json.loads(data)

    async with AsyncClient("http://127.0.0.1:7700", "masterKey") as client:
        plugins = AsyncIndexPlugins(
            add_documents_plugins=(ModifyDocumentPlugin(),),
            update_documents_plugins=(ModifyDocumentPlugin(),),
            search_plugins=(FilterSearchResultsPlugin(),),
        )
        index = await client.create_index("movies", primary_key="id", plugins=plugins)
        task = await index.add_documents(documents)
        await client.wait_for_task(task.task_uid)
        result = await index.search("cars")
        print(result)  # noqa: T201

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
