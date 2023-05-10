from __future__ import annotations

from functools import lru_cache
from pathlib import Path

try:
    import tomli as tomllib  # type: ignore
except ModuleNotFoundError:
    import tomllib  # type: ignore


@lru_cache(maxsize=1)
def get_version() -> str:
    pyproject = Path().absolute() / "pyproject.toml"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
        return data["tool"]["poetry"]["version"]
