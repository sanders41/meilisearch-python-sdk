from typing import Any, Dict, List, Optional

from camel_converter.pydantic_base import CamelBase


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


class Pagination(CamelBase):
    max_total_hits: int


class MeiliSearchSettings(CamelBase):
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
