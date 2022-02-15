# Meilisearch Python Async

[![Tests Status](https://github.com/sanders41/meilisearch-python-async/workflows/Testing/badge.svg?branch=main&event=push)](https://github.com/sanders41/meilisearch-python-async/actions?query=workflow%3ATesting+branch%3Amain+event%3Apush)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/sanders41/meilisearch-python-async/main.svg)](https://results.pre-commit.ci/latest/github/sanders41/meilisearch-python-async/main)
[![Coverage](https://codecov.io/github/sanders41/meilisearch-python-async/coverage.svg?branch=main)](https://codecov.io/gh/sanders41/meilisearch-python-async)
[![PyPI version](https://badge.fury.io/py/meilisearch-python-async.svg)](https://badge.fury.io/py/meilisearch-python-async)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/meilisearch-python-async?color=5cc141)](https://github.com/sanders41/meilisearch-python-async)

Meilisearch Python Async is a Python async client for the [Meilisearch](https://github.com/meilisearch/meilisearch) API. Meilisearch also has an official [Python client](https://github.com/meilisearch/meilisearch-python).

Which of the two clients to use comes down to your particular use case. The purpose for this async client is to allow for non-blocking calls when working in async frameworks such as [FastAPI](https://fastapi.tiangolo.com/), or if your own code base you are working in is async. If this does not match your use case then the official client will be a better choice.

## Installation

Using a virtual environmnet is recommended for installing this package. Once the virtual environment is created and activated install the package with:

```sh
pip install meilisearch-python-async
```

## Run Meilisearch

There are several ways to [run Meilisearch](https://docs.meilisearch.com/reference/features/installation.html#download-and-launch).
Pick the one that works best for your use case and then start the server.

As as example to use Docker:

```sh
docker pull getmeili/meilisearch:latest
docker run -it --rm -p 7700:7700 getmeili/meilisearch:latest ./meilisearch --master-key=masterKey
```

## Useage

### Add Documents

- Note: `client.index("books") creates an instance of an Index object but does not make a network call to send the data yet so it does not need to be awaited.

```py
from meilisearch_python_async import Client

async with Client('http://127.0.0.1:7700', 'masterKey') as client:
    index = client.index("books")

    documents = [
        {"id": 1, "title": "Ready Player One"},
        {"id": 42, "title": "The Hitchhiker's Guide to the Galaxy"},
    ]

    await index.add_documents(documents)
```

The server will return an update id that can be used to [get the status](https://docs.meilisearch.com/reference/api/updates.html#get-an-update-status)
of the updates. To do this you would save the result response from adding the documets to a variable,
this will be a UpdateId object, and use it to check the status of the updates.

```py
update = await index.add_documents(documents)
status = await client.index('books').get_update_status(update.update_id)
```

### Basic Searching

```py
search_result = await index.search("ready player")
```

### Base Search Results: SearchResults object with values

```py
SearchResults(
    hits = [
        {
            "id": 1,
            "title": "Ready Player One",
        },
    ],
    offset = 0,
    limit = 20,
    nb_hits = 1,
    exhaustive_nb_hits = bool,
    facets_distributionn = None,
    processing_time_ms = 1,
    query = "ready player",
)
```

### Custom Search

Information about the parameters can be found in the [search parameters](https://docs.meilisearch.com/reference/features/search_parameters.html) section of the documentation.

```py
index.search(
    "guide",
    attributes_to_highlight=["title"],
    filters="book_id > 10"
)
```

### Custom Search Results: SearchResults object with values

```py
SearchResults(
    hits = [
        {
            "id": 42,
            "title": "The Hitchhiker's Guide to the Galaxy",
            "_formatted": {
                "id": 42,
                "title": "The Hitchhiker's Guide to the <em>Galaxy</em>"
            }
        },
    ],
    offset = 0,
    limit = 20,
    nb_hits = 1,
    exhaustive_nb_hits = bool,
    facets_distributionn = None,
    processing_time_ms = 5,
    query = "galaxy",
)
```

## Documentation

See our [docs](https://meilisearch-python-async.paulsanders.dev) for the full documentation.

## Compatibility with Meilisearch

This package only guarantees the compatibility with [version v0.26 of Meilisearch](https://github.com/meilisearch/MeiliSearch/releases/tag/v0.26.0).

## Contributing

Contributions to this project are welcome. If you are interesting in contributing please see our [contributing guide](CONTRIBUTING.md)
