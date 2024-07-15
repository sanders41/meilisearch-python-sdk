from meilisearch_python_sdk import Client
from meilisearch_python_sdk.json_handler import UjsonHandler


def main() -> int:
    client = Client("http://127.0.0.1:7700", "masterKey", json_handler=UjsonHandler())
    index = client.create_index("movies", primary_key="id")
    index.add_documents_from_file("../datasets/small_movies.json")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
