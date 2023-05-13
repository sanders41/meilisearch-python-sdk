from typing import Any, Dict, List

from camel_converter.pydantic_base import CamelBase


class DocumentFilter(CamelBase):
    field: str
    filter: str


class DocumentsInfo(CamelBase):
    results: List[Dict[str, Any]]
    offset: int
    limit: int
    total: int
