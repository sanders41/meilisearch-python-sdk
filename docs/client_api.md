## `client` Usage

### Create a client

To create a client:

```py
from milisearch_python_sdk import Client


client = Client("http://localhost:7700", "masterKey")
index = client.index("movies")
...
```

### Custom headers

Custom headers can be added to the client by adding them to `custom_headers` when creating the
client.

```py
from meilisearch_python_sdk import Client

client = Client(
    "http://127.0.0.1:7700",
    "masterKey",
    custom_headers={"header_key_1": "header_value_1", "header_key_2": "header_value_2"}
)
index = client.index("movies")
...
```

## `Client` API

::: meilisearch_python_sdk.Client
