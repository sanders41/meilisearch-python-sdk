## `Client Usage`

### Create a client

To create a client:

```py
from milisearch_python_sdk import Client


client = Client("http://localhost:7700", "masterKey")
index = client.index("movies")
...
```

## `Client API`

::: meilisearch_python_sdk._client.Client
