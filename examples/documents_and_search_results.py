from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from meilisearch_python_sdk import Client
from meilisearch_python_sdk.models.search import SearchResults
from meilisearch_python_sdk.plugins import Event, IndexPlugins
from meilisearch_python_sdk.types import JsonMapping


class ModifyDocumentPlugin:
    POST_EVENT = False
    PRE_EVENT = True  # Specifies the plugin should be run before adding documents

    def run_document_plugin(
        self, event: Event, *, documents: Sequence[JsonMapping], **kwargs: Any
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
    POST_EVENT = True  # Specifies the plugin should be run after the search
    PRE_EVENT = False

    def run_post_search_plugin(
        self, event: Event, *, search_results: SearchResults, **kwargs: Any
    ) -> SearchResults:
        filtered_hits = []
        for hit in search_results.hits:
            if hit["access"] != "admin":
                filtered_hits.append(hit)

        search_results.hits = filtered_hits

        return search_results


def main() -> int:
    with open("../datasets/small_movies.json") as f:
        documents = json.load(f)

    client = Client("http://127.0.0.1:7700", "masterKey")
    plugins = IndexPlugins(
        add_documents_plugins=(ModifyDocumentPlugin(),),
        update_documents_plugins=(ModifyDocumentPlugin(),),
        search_plugins=(FilterSearchResultsPlugin(),),
    )
    index = client.create_index("movies", primary_key="id", plugins=plugins)
    task = index.add_documents(documents)
    client.wait_for_task(task.task_uid)
    result = index.search("cars")
    print(result)  # noqa: T201

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
