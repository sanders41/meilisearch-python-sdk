from meilisearch_python_sdk import __version__
from meilisearch_python_sdk._http_requests import user_agent


def test_user_agent():
    assert user_agent() == f"Meilisearch Python SDK (v{__version__})"
