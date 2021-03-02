# Async Search Client

[![Tests Status](https://github.com/sanders41/async-search-client/workflows/Testing/badge.svg?branch=main&event=push)](https://github.com/sanders41/async-search-client/actions?query=workflow%3ATesting+branch%3Amain+event%3Apush)
[![Lint Status](https://github.com/sanders41/async-search-client/workflows/Linting/badge.svg?branch=main&event=push)](https://github.com/sanders41/async-search-client/actions?query=workflow%3ALinting+branch%3Amain+event%3Apush)
[![Coverage](https://codecov.io/github/sanders41/async-search-client/coverage.svg?branch=main)](https://codecov.io/gh/sanders41/async-search-client)
[![PyPI version](https://badge.fury.io/py/async-search-client.svg)](https://badge.fury.io/py/async-search-client)

Async Serach Client is a Python async client for the [MeiliSearch](https://github.com/meilisearch/MeiliSearch) API. MeiliSearch also has an official [Python client](https://github.com/meilisearch/meilisearch-python).

Which of the two clients to use comes down to your particular use case. The purpose for this async client is to allow for non-blocking calls when you are working in async frameworks such as [FastAPI](https://fastapi.tiangolo.com/), or if your own code base you are working in is async. If this does not match your use case then the official client will be a better choice.

For the most part this client mirrors the functionality of the official client and the same [documenation](https://docs.meilisearch.com/reference/) will apply. There are are few exceptions to this to be aware of:

1. The async client runs in a context manager. This means to create a client, instead of:

    ```py
    client = Client("http://127.0.0.1:7700", "masterKey")
    ```

    In the async client it would be:

    ```py
    async with Client("http://127.0.0.1:7700", "masterKey") as client:
        ...
    ```

2. Because this client is async you need to await the calls. For example adding documents in the official verison would be:

    ```py
    index.add_documents(documents)
    ```

    In the async client it would be:

    ```py
    await index.add_documents(documents)
    ```

3. The async client uses [Pydantic](https://pydantic-docs.helpmanual.io/) to serialize/deserialize the JSON from MeiliSearch into python objects wherever possible, and in the process converts the camelCaseNames from JSON into more Pythonic snake_case_names. The official client uses dictionaries to store the return values in most cases.

## Installation

Using a virtual environmnet is recommended for installing this package. Once the virtual environment is created and activated install the package with:

```sh
pip install async-search-client
```

## Run MeiliSearch

There are several ways to [run MeiliSearch](https://docs.meilisearch.com/reference/features/installation.html#download-and-launch). Pick the one that works best for your use case and then start the server.

As as example to use Docker:

```sh
docker pull getmeili/meilisearch:latest
docker run -it --rm -p 7700:7700 getmeili/meilisearch:latest ./meilisearch --master-key=masterKey
```

## Useage

### Add Documents

* Note: `client.index("books") creates an instance of an Index object but does not make a network call to send the data yet so it does not need to be awaited.

```py
from async_search_client import Client

async with Client('http://127.0.0.1:7700', 'masterKey') as client:
    index = client.index("books")

    documents = [
        {"id": 1, "title": "Ready Player One"},
        {"id": 42, "title": "The Hitchhiker's Guide to the Galaxy"},
    ]

    await index.add_documents(documents)
```

The server will return a update id that can be used to [get the status](https://docs.meilisearch.com/reference/api/updates.html#get-an-update-status) of the updates. To do this you would save the result response from adding the documets to a variable, this will be a UpdateId object, and use it to check the status of the updates.

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

## Learn More

For more see the [API Reference](https://docs.meilisearch.com/reference/api/) in the MeiliSearch documentation. Keep in mind you will need to await the examples shown in the documentation, and that you will be getting python objects instead of JSON for you results.

## Contributing

Contributions to this project are welcome. If you are interesting in contributing please see our [contributing guide](CONTRIBUTING.md)
