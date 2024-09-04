from __future__ import annotations

import json
from typing import Any

from meilisearch_python_sdk import Client
from meilisearch_python_sdk.decorators import ConnectionInfo, add_documents


@add_documents(
    index_name="movies",
    connection_info=ConnectionInfo(url="http://127.0.0.1:7700", api_key="masterKey"),
)
def load_documents() -> list[dict[str, Any]]:
    with open("../datasets/small_movies.json") as f:
        documents = json.load(f)

    return documents


def main() -> int:
    client = Client("http://127.0.0.1:7700", "masterKey")
    index = client.create_index("movies", "id")
    load_documents()
    documents = index.get_documents()

    print(documents)  # noqa: T201

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
