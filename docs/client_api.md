## `Client Usage`

### Create a client

To create a client:

```py
from milisearch-python-async import Client


client = Client("http://localhost:7700", "masterKey")
index = client.index("movies")
...
```

## `Client API`

::: meilisearch_python_async._client.Client
