import json

from meilisearch_python_sdk import Client
from meilisearch_python_sdk.models.settings import MeilisearchSettings


def main() -> int:
    with open("../datasets/small_movies.json") as f:
        documents = json.load(f)

    client = Client("http://127.0.0.1:7700", "masterKey")
    index = client.create_index("movies", primary_key="id")
    settings = MeilisearchSettings(
        filterable_attributes=["genre"], searchable_attributes=["title", "genre", "overview"]
    )

    # Notice that the settings are updated before indexing the documents. Updating settings
    # after adding the documnts will cause the documents to be reindexed, which will be much
    # slower because the documents will have to be indexed twice.
    task = index.update_settings(settings)
    client.wait_for_task(task.task_uid)
    index.add_documents(documents)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
