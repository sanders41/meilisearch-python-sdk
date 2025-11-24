from __future__ import annotations

from collections.abc import Generator, MutableMapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlencode

from meilisearch_python_sdk._utils import iso_to_date_time
from meilisearch_python_sdk.errors import MeilisearchError
from meilisearch_python_sdk.json_handler import BuiltinHandler, OrjsonHandler, UjsonHandler
from meilisearch_python_sdk.models.search import (
    Hybrid,
)
from meilisearch_python_sdk.models.settings import (
    CompositeEmbedder,
    Embedders,
    HuggingFaceEmbedder,
    OllamaEmbedder,
    OpenAiEmbedder,
    RestEmbedder,
    UserProvidedEmbedder,
)
from meilisearch_python_sdk.plugins import (
    AsyncDocumentPlugin,
    AsyncPlugin,
    AsyncPostSearchPlugin,
    DocumentPlugin,
    Plugin,
    PostSearchPlugin,
)
from meilisearch_python_sdk.types import JsonDict

if TYPE_CHECKING:  # pragma: no cover
    import sys

    from meilisearch_python_sdk.types import Filter, JsonMapping

    if sys.version_info >= (3, 11):
        pass
    else:
        pass


class BaseIndex:
    def __init__(
        self,
        uid: str,
        primary_key: str | None = None,
        created_at: str | datetime | None = None,
        updated_at: str | datetime | None = None,
        json_handler: BuiltinHandler | OrjsonHandler | UjsonHandler | None = None,
        hits_type: Any = JsonDict,
    ):
        self.uid = uid
        self.primary_key = primary_key
        self.created_at: datetime | None = iso_to_date_time(created_at)
        self.updated_at: datetime | None = iso_to_date_time(updated_at)
        self.hits_type = hits_type
        self._base_url = "indexes/"
        self._base_url_with_uid = f"{self._base_url}{self.uid}"
        self._documents_url = f"{self._base_url_with_uid}/documents"
        self._stats_url = f"{self._base_url_with_uid}/stats"
        self._settings_url = f"{self._base_url_with_uid}/settings"
        self._json_handler = json_handler if json_handler else BuiltinHandler()

    def __str__(self) -> str:
        return f"{type(self).__name__}(uid={self.uid}, primary_key={self.primary_key}, created_at={self.created_at}, updated_at={self.updated_at})"

    def __repr__(self) -> str:
        return f"{type(self).__name__}(uid={self.uid!r}, primary_key={self.primary_key!r}, created_at={self.created_at!r}, updated_at={self.updated_at!r})"

    def _set_fetch_info(
        self, primary_key: str, created_at_iso_str: str, updated_at_iso_str: str
    ) -> None:
        self.primary_key = primary_key
        self.created_at = iso_to_date_time(created_at_iso_str)
        self.updated_at = iso_to_date_time(updated_at_iso_str)


def batch(
    documents: Sequence[MutableMapping], batch_size: int
) -> Generator[Sequence[MutableMapping], None, None]:
    total_len = len(documents)
    for i in range(0, total_len, batch_size):
        yield documents[i : i + batch_size]


def combine_documents(documents: list[list[Any]]) -> list[Any]:
    return [x for y in documents for x in y]


def plugin_has_method(
    plugin: AsyncPlugin
    | AsyncDocumentPlugin
    | AsyncPostSearchPlugin
    | Plugin
    | DocumentPlugin
    | PostSearchPlugin,
    method: str,
) -> bool:
    check = getattr(plugin, method, None)
    if callable(check):
        return True

    return False


def raise_on_no_documents(
    documents: list[Any], document_type: str, directory_path: str | Path
) -> None:
    if not documents:
        raise MeilisearchError(f"No {document_type} files found in {directory_path}")


def process_search_parameters(
    *,
    q: str | None = None,
    facet_name: str | None = None,
    facet_query: str | None = None,
    offset: int = 0,
    limit: int = 20,
    filter: Filter | None = None,
    facets: list[str] | None = None,
    attributes_to_retrieve: list[str] | None = None,
    attributes_to_crop: list[str] | None = None,
    crop_length: int = 200,
    attributes_to_highlight: list[str] | None = None,
    sort: list[str] | None = None,
    show_matches_position: bool = False,
    highlight_pre_tag: str = "<em>",
    highlight_post_tag: str = "</em>",
    crop_marker: str = "...",
    matching_strategy: Literal["all", "last", "frequency"] = "last",
    hits_per_page: int | None = None,
    page: int | None = None,
    attributes_to_search_on: list[str] | None = None,
    distinct: str | None = None,
    show_ranking_score: bool = False,
    show_ranking_score_details: bool = False,
    ranking_score_threshold: float | None = None,
    vector: list[float] | None = None,
    hybrid: Hybrid | None = None,
    locales: list[str] | None = None,
    retrieve_vectors: bool | None = None,
    exhaustive_facet_count: bool | None = None,
    media: JsonMapping | None = None,
) -> JsonDict:
    if attributes_to_retrieve is None:
        attributes_to_retrieve = ["*"]

    body: JsonDict = {
        "q": q,
        "offset": offset,
        "limit": limit,
        "filter": filter,
        "facets": facets,
        "attributesToRetrieve": attributes_to_retrieve,
        "attributesToCrop": attributes_to_crop,
        "cropLength": crop_length,
        "attributesToHighlight": attributes_to_highlight,
        "sort": sort,
        "showMatchesPosition": show_matches_position,
        "highlightPreTag": highlight_pre_tag,
        "highlightPostTag": highlight_post_tag,
        "cropMarker": crop_marker,
        "matchingStrategy": matching_strategy,
        "hitsPerPage": hits_per_page,
        "page": page,
        "attributesToSearchOn": attributes_to_search_on,
        "showRankingScore": show_ranking_score,
        "rankingScoreThreshold": ranking_score_threshold,
    }

    if facet_name:
        body["facetName"] = facet_name

    if facet_query:
        body["facetQuery"] = facet_query

    if distinct:
        body["distinct"] = distinct

    if show_ranking_score_details:
        body["showRankingScoreDetails"] = show_ranking_score_details

    if vector:
        body["vector"] = vector

    if hybrid:
        body["hybrid"] = hybrid.model_dump(by_alias=True)

    if locales:
        body["locales"] = locales

    if retrieve_vectors is not None:
        body["retrieveVectors"] = retrieve_vectors

    if exhaustive_facet_count is not None:
        body["exhaustivefacetCount"] = exhaustive_facet_count

    if media is not None:
        body["media"] = media

    return body


def build_encoded_url(base_url: str, params: JsonMapping) -> str:
    return f"{base_url}?{urlencode(params)}"


# TODO: Add back after embedder setting issue fixed https://github.com/meilisearch/meilisearch/issues/4585
def embedder_json_to_embedders_model(  # pragma: no cover
    embedder_json: JsonDict | None,
) -> Embedders | None:
    if not embedder_json:  # pragma: no cover
        return None

    embedders: dict[
        str,
        OpenAiEmbedder
        | HuggingFaceEmbedder
        | OllamaEmbedder
        | RestEmbedder
        | UserProvidedEmbedder
        | CompositeEmbedder,
    ] = {}
    for k, v in embedder_json.items():
        if v.get("source") == "openAi":
            embedders[k] = OpenAiEmbedder(**v)
        elif v.get("source") == "huggingFace":
            embedders[k] = HuggingFaceEmbedder(**v)
        elif v.get("source") == "ollama":
            embedders[k] = OllamaEmbedder(**v)
        elif v.get("source") == "rest":
            embedders[k] = RestEmbedder(**v)
        elif v.get("source") == "composit":
            embedders[k] = CompositeEmbedder(**v)
        else:
            embedders[k] = UserProvidedEmbedder(**v)

    return Embedders(embedders=embedders)


# TODO: Add back after embedder setting issue fixed https://github.com/meilisearch/meilisearch/issues/4585
def embedder_json_to_settings_model(  # pragma: no cover
    embedder_json: JsonDict | None,
) -> (
    dict[
        str,
        OpenAiEmbedder
        | HuggingFaceEmbedder
        | OllamaEmbedder
        | RestEmbedder
        | UserProvidedEmbedder
        | CompositeEmbedder,
    ]
    | None
):
    if not embedder_json:  # pragma: no cover
        return None

    embedders: dict[
        str,
        OpenAiEmbedder
        | HuggingFaceEmbedder
        | OllamaEmbedder
        | RestEmbedder
        | UserProvidedEmbedder
        | CompositeEmbedder,
    ] = {}
    for k, v in embedder_json.items():
        if v.get("source") == "openAi":
            embedders[k] = OpenAiEmbedder(**v)
        elif v.get("source") == "huggingFace":
            embedders[k] = HuggingFaceEmbedder(**v)
        elif v.get("source") == "ollama":
            embedders[k] = OllamaEmbedder(**v)
        elif v.get("source") == "rest":
            embedders[k] = RestEmbedder(**v)
        elif v.get("source") == "composit":
            embedders[k] = CompositeEmbedder(**v)
        else:
            embedders[k] = UserProvidedEmbedder(**v)

    return embedders


def validate_file_type(file_path: Path) -> None:
    if file_path.suffix not in (".json", ".csv", ".ndjson"):
        raise MeilisearchError("File must be a json, ndjson, or csv file")


def validate_ranking_score_threshold(ranking_score_threshold: float) -> None:
    if not 0.0 <= ranking_score_threshold <= 1.0:
        raise MeilisearchError("ranking_score_threshold must be between 0.0 and 1.0")
