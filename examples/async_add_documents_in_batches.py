import asyncio
import json

from meilisearch_python_sdk import AsyncClient


async def main() -> int:
    with open("datasets/small_movies.json") as f:
        documents = json.load(f)

    async with AsyncClient("http://127.0.0.1:7700", "masterKey") as client:
        index = client.index("movies")

        # Meilisearch prefers larger batch sizes so set this as large as you can.
        await index.add_documents_in_batches(documents, primary_key="id", batch_size=1000)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
