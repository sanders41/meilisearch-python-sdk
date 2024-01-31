# Plugins

Plugins can be used to extend the functionality of certain methods, currently plugins are only
supported for indexes. To create plugins you creat a class that implements the Protocol for the
plugin, then add an instance of your class to the plugins when creating an index. Passing protocols
is done through a named tuple that specifies where the plugin should run. The options are:

- add_documents_plugins: Runs the plugins when adding documents. This runs for all the add documents
  methods, i.e. `add_documents_in_batches`.
- delete_all_documents_plugins: Run on the `delete_all_documents` method.
- delete_document_plugins: Run on the `delete_document` method.
- delete_documents_plugins: Run on the `delete_documents` method.
- delete_documents_by_filter_plugins: Run on the `delete_documents_by_filter` method.
- search_plugins: Run on the `search` and `facet_search` methods.
- update_documents_plugins: Run on the `update_document` method.

When creating your plugin you specify if you want it to run before or after the default
functionality. Additionaly plugins for async indexes can be run concurrently with the default
functionality.

## Examples:

### Search metrics

It is common to want to know what users are searching for, however Meilisearch doesn't provide a
way to track this out of the box. A search plugin could be used to implement this functionality
yourself.

Note that in these examples the protocol is satisfied by providing the `CONNECURRENT_EVENT`,
`POST_EVENT`, and `PRE_EVENT` vairables and the
`async def run_plugin(self, event: AsyncEvent, **kwargs: Any) -> None:` method for an async index,
or the `POST_EVENT` and `PRE_EVENT` vairables , and
`def run_plugin(self, event: Event, **kwargs: Any) -> None:` method for a non-async index. You
class can contain any additional methods/variables needed as long as the protocol requirements
have been satisfied.

#### Async index

```py
import asyncio
import json
import sqlite3
from typing import Any

from meilisearch_python_sdk import AsyncClient
from meilisearch_python_sdk.plugins import AsyncEvent, AsyncIndexPlugins


class SearchTrackerPlugin:
    CONCURRENT_EVENT = True  # Specifies the plugin should be run concurrently with the search
    POST_EVENT = False
    PRE_EVENT = False

    def __init__(self) -> None:
        self.conn = sqlite3.Connection("examples/search_tracker.db")
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


async def main() -> int:
    with open("datasets/small_movies.json") as f:
        documents = json.load(f)

    client = AsyncClient("http://127.0.0.1:7700", "masterKey")
    plugins = AsyncIndexPlugins(search_plugins=(SearchTrackerPlugin(),))
    index = await client.create_index("movies", primary_key="id", plugins=plugins)
    task = await index.add_documents(documents)
    await client.wait_for_task(task.task_uid)
    result = await index.search("Cars")
    print(result)  # noqa: T201

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

#### Index

```py
import json
import sqlite3
from typing import Any

from meilisearch_python_sdk import Client
from meilisearch_python_sdk.plugins import Event, IndexPlugins


class SearchTrackerPlugin:
    POST_EVENT = False
    PRE_EVENT = True  # Specifies the plugin should be run before the search

    def __init__(self) -> None:
        self.conn = sqlite3.Connection("examples/search_tracker.db")
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
    with open("datasets/small_movies.json") as f:
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
```

### Modify documents and search results

A pre event plugin can be used to modify the documents before sending for indexing. In this example
a new `access` field will be added to the doocuments before they are added or updated. The example
will set every other record to `admin` access with the other records being set to `read`. This will
illustrate the idea of modifing documents even it if doesn't make real world sense.

A post search plugin, this type of search plugin can only be used post search because it requires
the result of the search, will be used to remove records marked as `admin` before returing the result.
In the real world this filtering would probably be done with a filterable field in Meilisearch,but
again, this is just used here to illustrate the idea.

#### Async Index

```py
import asyncio
import json
from typing import Any, Sequence

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
    with open("datasets/small_movies.json") as f:
        documents = json.load(f)

    client = AsyncClient("http://127.0.0.1:7700", "masterKey")
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
```

#### Index

```py
import json
from typing import Any, Sequence

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
    with open("datasets/small_movies.json") as f:
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
```
