from typing import Any, Dict, List, Optional

import pydantic
from camel_converter.pydantic_base import CamelBase

from meilisearch_python_async._utils import is_pydantic_2


class MinWordSizeForTypos(CamelBase):
    one_typo: Optional[int] = None
    two_typos: Optional[int] = None


class TypoTolerance(CamelBase):
    enabled: bool = True
    disable_on_attributes: Optional[List[str]] = None
    disable_on_words: Optional[List[str]] = None
    min_word_size_for_typos: Optional[MinWordSizeForTypos] = None


class Faceting(CamelBase):
    max_values_per_facet: int
    sort_facet_values_by: Optional[Dict[str, str]] = None

    if is_pydantic_2():

        @pydantic.field_validator("sort_facet_values_by")  # type: ignore[attr-defined]
        @classmethod
        def validate_facet_order(cls, v: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
            if not v:  # pragma: no cover
                return None

            for _, value in v.items():
                if value not in ("alpha", "count"):
                    raise ValueError('facet_order must be either "alpha" or "count"')

            return v

    else:  # pragma: no cover

        @pydantic.validator("sort_facet_values_by")  # type: ignore[attr-defined]
        @classmethod
        def validate_facet_order(cls, v: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
            if not v:
                return None

            for _, value in v.items():
                if value not in ("alpha", "count"):
                    raise ValueError('facet_order must be either "alpha" or "count"')

            return v


class Pagination(CamelBase):
    max_total_hits: int


class MeilisearchSettings(CamelBase):
    synonyms: Optional[Dict[str, Any]] = None
    stop_words: Optional[List[str]] = None
    ranking_rules: Optional[List[str]] = None
    filterable_attributes: Optional[List[str]] = None
    distinct_attribute: Optional[str] = None
    searchable_attributes: Optional[List[str]] = None
    displayed_attributes: Optional[List[str]] = None
    sortable_attributes: Optional[List[str]] = None
    typo_tolerance: Optional[TypoTolerance] = None
    faceting: Optional[Faceting] = None
    pagination: Optional[Pagination] = None
