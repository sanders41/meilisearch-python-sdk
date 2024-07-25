## `AsyncClient` Usage

### Create a client with a context manager

This client runs in a context manager which ensures that everything is cleaned up after the use of
the client is done. To create a client:

```py
from meilisearch-python-sdk import AsyncClient


async with AsyncClient("http://localhost:7700", "masterKey") as client:
    index = client.index("movies")
    ...
```

### Custom headers

Custom headers can be added to the client by adding them to `custom_headers` when creating the
client.

```py
from meilisearch_python_sdk import AsyncClient

async with AsyncClient(
    "http://127.0.0.1:7700",
    "masterKey",
    custom_headers={"header_key_1": "header_value_1", "header_key_2": "header_value_2"}
) as client:
    index = client.index("movies")
    ...
```

### Create a client without a context manager

It is also possible to call the client without using a context manager, but in doing so you will
need to make sure to do the cleanup yourself:

```py
from meilisearch-python-sdk import AsyncClient


try:
    client = AsyncClient("http://localhost:7700", "masterKey")
    ...
finally:
    await client.aclose()

```

## `AsyncClient` API

::: meilisearch_python_sdk.AsyncClient
