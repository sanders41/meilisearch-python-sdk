from __future__ import annotations

import json

from meilisearch_python_sdk import Client


def main() -> int:
    with open("../datasets/small_movies.json") as f:
        documents = json.load(f)

    client = Client("http://127.0.0.1:7700", "masterKey")
    index = client.index("movies")

    # Meilisearch prefers larger batch sizes so set this as large as you can.
    index.add_documents_in_batches(documents, primary_key="id", batch_size=1000)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
