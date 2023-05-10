from pathlib import Path

from meilisearch_python_async import __version__
from meilisearch_python_async._http_requests import user_agent
from meilisearch_python_async._version import VERSION

try:
    import tomli as tomllib  # type: ignore
except ModuleNotFoundError:
    import tomllib  # type: ignore


def test_versions_match():
    pyproject = Path().absolute() / "pyproject.toml"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
        pyproject_version = data["tool"]["poetry"]["version"]

    assert VERSION == pyproject_version


def test_user_agent():
    assert user_agent() == f"Meilisearch Python Async (v{__version__})"
