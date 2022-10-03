## `Client Usage`

### Create a client with a context manager

This client runs in a context manager which ensures that everything is cleaned up after the use of
the client is done. To create a client:

```py
from milisearch-python-async import Client


async with Client("http://localhost:7700", "masterKey") as client:
    index = client.index("movies")
    ...
```

### Create a client without a context manager

It is also possible to call the client without using a context manager, but in doing so you will
need to make sure to do the cleanup yourself:

```py
from meilisearch-python-async import Client


try:
    client = Client("http://localhost:7700", "masterKey")
    ...
finally:
    await client.aclose()

```

## `Client API`

::: meilisearch_python_async.client.Client
