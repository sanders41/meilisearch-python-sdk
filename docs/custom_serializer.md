# Custom Serializer

In some cases your documents will contain types that the Python JSON serializer does not know how
to handle. When this happens you can provide your own custom serializer.

## Example

```py
from datetime import datetime
from json import JSONEncoder
from uuid import uuid4

from meilisearch_python_sdk import Client


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
client = Client("http://127.0.0.1:7700")
index = client.index("movies", primary_key="id")
index.add_documents(documents, serializer=CustomEncoder)
```
