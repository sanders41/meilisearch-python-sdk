# JSON Handler

For json loads and dumps you have the option to use the `json` module from the standard libary,
orjson, or ujson. This done by setting the `json_handler` when creating the `AsyncClient` or
`Client`. By default the standard library `json` module will be used. The examples below use
`Client`, and the same options are available for `AsyncClient`.

## Standard Library `json` Module

### Custom Serializer

In some cases your documents will contain types that the Python JSON serializer does not know how
to handle. When this happens you can provide your own custom serializer when using the `json`
module.

### Example

```py
from datetime import datetime
from json import JSONEncoder
from uuid import uuid4

from meilisearch_python_sdk import Client
from meilisearch_python_sdk.json_handler import BuiltinHandler


class CustomEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, (UUID, datetime)):
            return str(o)

        # Let the base class default method raise the TypeError
        return super().default(o)


documents = [
    {"id": uuid4(), "title": "test 1", "when": datetime.now()},
    {"id": uuid4(), "title": "Test 2", "when": datetime.now()},
]
client = Client("http://127.0.0.1:7700", json_handler=BuiltinHandler(serializer=CustomEncoder))
index = client.index("movies", primary_key="id")
index.add_documents(documents)
```

## orjson

### Example

```py
from uuid import uuid4

from meilisearch_python_sdk import Client
from meilisearch_python_sdk.json_handler import OrjsonHandler


documents = [
    {"id": uuid4(), "title": "test 1"},
    {"id": uuid4(), "title": "Test 2"},
]
client = Client("http://127.0.0.1:7700", json_handler=OrjsonHandler())
index = client.index("movies", primary_key="id")
index.add_documents(documents)
```

## ujson

### Example

```py
from uuid import uuid4

from meilisearch_python_sdk import Client
from meilisearch_python_sdk.json_handler import UjsonHandler


documents = [
    {"id": uuid4(), "title": "test 1"},
    {"id": uuid4(), "title": "Test 2"},
]
client = Client("http://127.0.0.1:7700", json_handler=UjsonHandler())
index = client.index("movies", primary_key="id")
index.add_documents(documents)
```
