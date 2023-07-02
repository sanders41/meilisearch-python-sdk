from datetime import datetime
from typing import Dict, Optional

import pydantic
from camel_converter.pydantic_base import CamelBase

from meilisearch_python_async._utils import is_pydantic_2, iso_to_date_time


class IndexBase(CamelBase):
    uid: str
    primary_key: Optional[str]


class IndexInfo(IndexBase):
    created_at: datetime
    updated_at: datetime

    if is_pydantic_2():

        @pydantic.field_validator("created_at", mode="before")  # type: ignore[attr-defined]
        @classmethod
        def validate_created_at(cls, v: str) -> datetime:
            converted = iso_to_date_time(v)

            if not converted:  # pragma: no cover
                raise ValueError("created_at is required")

            return converted

        @pydantic.field_validator("updated_at", mode="before")  # type: ignore[attr-defined]
        @classmethod
        def validate_updated_at(cls, v: str) -> datetime:
            converted = iso_to_date_time(v)

            if not converted:  # pragma: no cover
                raise ValueError("updated_at is required")

            return converted

    else:  # pragma: no cover

        @pydantic.validator("created_at", pre=True)
        @classmethod
        def validate_created_at(cls, v: str) -> datetime:
            converted = iso_to_date_time(v)

            if not converted:
                raise ValueError("created_at is required")

            return converted

        @pydantic.validator("updated_at", pre=True)
        @classmethod
        def validate_updated_at(cls, v: str) -> datetime:
            converted = iso_to_date_time(v)

            if not converted:
                raise ValueError("updated_at is required")

            return converted


class IndexStats(CamelBase):
    number_of_documents: int
    is_indexing: bool
    field_distribution: Dict[str, int]
