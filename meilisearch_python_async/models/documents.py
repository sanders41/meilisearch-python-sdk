from typing import Any, Dict, List

from camel_converter.pydantic_base import CamelBase


class DocumentsInfo(CamelBase):
    results: List[Dict[str, Any]]
    offset: int
    limit: int
    total: int
