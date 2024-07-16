from __future__ import annotations

from camel_converter.pydantic_base import CamelBase

from meilisearch_python_sdk.types import JsonDict


class DocumentsInfo(CamelBase):
    results: list[JsonDict]
    offset: int
    limit: int
    total: int
