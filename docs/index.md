# Meilisearch Python SDK

Meilisearch Python SDK provides both an async and sync client for the
[Meilisearch](https://github.com/meilisearch/meilisearch) API.

The focus of this documentation is on the Meilisearch Python SDK API. More information of
Meilisearch itself and how to use it can be found at [https://www.meilisearch.com/docs](https://www.meilisearch.com/docs).

## Which client to chose

If the code base you are working with uses asyncio, for example if you are using
[FastAPI](https://fastapi.tiangolo.com/), chose the `AsyncClint` otherwise chose the `Client`.
The functionality of the two clients is the same, the difference being the `AsyncClient` provides
async methods and uses the `AsyncIndex`, which also provides async methods, while the `Client`
provides blocking methods and uses the `Index`, which also provides blocking methods.

## Instillation

Using a virtual environment is recommended for installing this package. Once the virtual
environment is created and activated, install the package with:

```sh
pip install meilisearch-python-sdk
```

Installing with the orjson extra will make JSON serilization/deserilization faster.

```sh
pip install meilisearch-python-sdk[orjson]
```

## Run Meilisearch

This package talks to a running Meilisearch server, so you will need one to connect to. There are
several ways to
[run Meilisearch](https://www.meilisearch.com/docs/learn/getting_started/installation), pick the
one that works best for your use case and then start the server. As an example, to use Docker:

```sh
docker pull getmeili/meilisearch:latest
docker run -it --rm -p 7700:7700 getmeili/meilisearch:latest ./meilisearch --master-key=masterKey
```

## Quickstart

The examples below add two documents to a `books` index and then search it. Note that
`client.index("books")` creates an index instance but does not make a network call, so with the
`AsyncClient` it does not need to be awaited.

### AsyncClient

```py
import asyncio

from meilisearch_python_sdk import AsyncClient


async def main() -> None:
    async with AsyncClient("http://127.0.0.1:7700", "masterKey") as client:
        index = client.index("books")

        documents = [
            {"id": 1, "title": "Ready Player One"},
            {"id": 42, "title": "The Hitchhiker's Guide to the Galaxy"},
        ]

        task = await index.add_documents(documents)
        await client.wait_for_task(task.task_uid)

        result = await index.search("ready player")
        print(result.hits)


asyncio.run(main())
```

### Client

```py
from meilisearch_python_sdk import Client


with Client("http://127.0.0.1:7700", "masterKey") as client:
    index = client.index("books")

    documents = [
        {"id": 1, "title": "Ready Player One"},
        {"id": 42, "title": "The Hitchhiker's Guide to the Galaxy"},
    ]

    task = index.add_documents(documents)
    client.wait_for_task(task.task_uid)

    result = index.search("ready player")
    print(result.hits)
```

## Waiting on tasks

Meilisearch processes writes asynchronously, so methods that modify data return a
[`TaskInfo`](models_task.md) instead of the result of the write. The `task_uid` on it can be used
to wait for the write to finish, or to check on its status later.

```py
task = index.add_documents([{"id": 1, "title": "Ready Player One"}])
result = client.wait_for_task(task.task_uid)
```

If you would rather check the status yourself instead of blocking, use `get_task`.

```py
task = index.add_documents([{"id": 1, "title": "Ready Player One"}])
status = client.get_task(task.task_uid)
```

The `AsyncClient` provides the same methods as awaitables.

## Search results

Searching returns a [`SearchResults`](models_search.md) object. The matching documents are in
`hits`, and the remaining fields describe the search that was run.

```py
SearchResults(
    hits=[
        {
            "id": 1,
            "title": "Ready Player One",
        },
    ],
    offset=0,
    limit=20,
    estimated_total_hits=1,
    processing_time_ms=1,
    query="ready player",
    facet_distribution=None,
    facet_stats=None,
    total_pages=None,
    total_hits=None,
    page=None,
    hits_per_page=None,
    semantic_hit_count=None,
    query_vector=None,
    performance_details=None,
)
```

## Custom search

`search` accepts the Meilisearch
[search parameters](https://www.meilisearch.com/docs/reference/api/search/search-with-post) as
keyword arguments. For example, to highlight the matching terms in the title and only return books
with an `id` above 10:

```py
index.search(
    "guide",
    attributes_to_highlight=["title"],
    filter="id > 10",
)
```

The highlighted values are added to each hit in a `_formatted` key.

```py
SearchResults(
    hits=[
        {
            "id": 42,
            "title": "The Hitchhiker's Guide to the Galaxy",
            "_formatted": {
                "id": "42",
                "title": "The Hitchhiker's <em>Guide</em> to the Galaxy",
            },
        },
    ],
    offset=0,
    limit=20,
    estimated_total_hits=1,
    processing_time_ms=5,
    query="guide",
    facet_distribution=None,
    facet_stats=None,
    total_pages=None,
    total_hits=None,
    page=None,
    hits_per_page=None,
    semantic_hit_count=None,
    query_vector=None,
    performance_details=None,
)
```

Note that filtering only works on attributes that have been added to the index's filterable
attributes first, otherwise Meilisearch returns an error.

```py
task = index.update_filterable_attributes(["id"])
client.wait_for_task(task.task_uid)
```

See the [settings models](models_settings.md) for the rest of the settings that can be updated.

## Where to go next

- [AsyncClient](async_client_api.md) and [Client](client_api.md) for the server level methods,
  such as managing indexes, API keys, and tasks.
- [AsyncIndex](async_index_api.md) and [Index](index_api.md) for the methods that work with
  documents, searching, and index settings.
- [Search models](models_search.md), [settings models](models_settings.md),
  [index models](models_index.md), [task models](models_task.md), and
  [client models](models_client.md) for the objects the methods accept and return.
- [Errors](errors_api.md) for the exceptions the SDK raises.
- [Plugins](plugins.md) for extending the behavior of the index methods.
- [JSON Handler](json_handler.md) for controlling JSON serialization, including using orjson.
- [Pydantic](pydantic.md) for deserializing your documents into your own Pydantic models.
- [Decorators](decorators_api.md) for the helpers provided for working with Meilisearch.
