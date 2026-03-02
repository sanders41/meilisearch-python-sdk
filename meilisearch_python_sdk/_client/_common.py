from __future__ import annotations

from typing import TYPE_CHECKING

from meilisearch_python_sdk.json_handler import BuiltinHandler, OrjsonHandler
from meilisearch_python_sdk.models.client import (
    KeyUpdate,
)
from meilisearch_python_sdk.models.search import (
    Federation,
    FederationMerged,
    SearchParams,
)
from meilisearch_python_sdk.types import JsonDict

if TYPE_CHECKING:
    from meilisearch_python_sdk.types import JsonMapping


def build_multi_search_payload(
    queries: list[SearchParams],
    federation: Federation | FederationMerged | None,
) -> tuple[list[JsonDict], JsonDict | None]:
    processed_queries: list[JsonDict] = []
    for query in queries:
        q = query.model_dump(by_alias=True)

        if query.retrieve_vectors is None:
            del q["retrieveVectors"]

        if federation:
            del q["limit"]
            del q["offset"]

        if query.media is None:
            del q["media"]

        if query.show_performance_details is None:
            del q["showPerformanceDetails"]

        processed_queries.append(q)

    if federation:
        federation_payload: JsonDict | None = federation.model_dump(by_alias=True)
        if federation_payload is not None and federation.facets_by_index is None:
            del federation_payload["facetsByIndex"]
    else:
        federation_payload = None

    return processed_queries, federation_payload


# No cover because it requires multiple instances of Meilisearch
def build_transfer_documents_payload(  # pragma: no cover
    url: str,
    api_key: str | None,
    payload_size: str | None,
    indexes: JsonMapping | None,
) -> JsonDict:
    payload: JsonDict = {"url": url}

    if api_key:
        payload["apiKey"] = api_key

    if payload_size:
        payload["payloadSize"] = payload_size

    if indexes:
        payload["indexes"] = indexes

    return payload


def build_swap_indexes_payload(indexes: list[tuple[str, str]], rename: bool) -> list[JsonDict]:
    if rename:
        return [{"indexes": x, "rename": True} for x in indexes]
    return [{"indexes": x} for x in indexes]


def build_offset_limit_url(base: str, offset: int | None, limit: int | None) -> str:
    if offset is not None and limit is not None:
        return f"{base}?offset={offset}&limit={limit}"
    elif offset is not None:
        return f"{base}?offset={offset}"
    elif limit is not None:
        return f"{base}?limit={limit}"

    return base


def build_update_key_payload(
    key: KeyUpdate, json_handler: BuiltinHandler | OrjsonHandler
) -> JsonDict:
    # The json_handler.loads(key.json()) is because Pydantic can't serialize a date in a Python dict,
    # but can when converting to a json string.
    return {
        k: v
        for k, v in json_handler.loads(key.model_dump_json(by_alias=True)).items()
        if v is not None and k != "key"
    }
