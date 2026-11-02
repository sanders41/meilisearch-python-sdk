from __future__ import annotations

import base64
import hashlib
import hmac
from calendar import timegm
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from httpx2 import AsyncClient as HttpxAsyncClient
from httpx2 import Client as HttpxClient

from meilisearch_python_sdk.json_handler import BuiltinHandler, OrjsonHandler

if TYPE_CHECKING:
    from meilisearch_python_sdk._client import AsyncClient, Client
    from meilisearch_python_sdk.types import JsonDict


def get_async_client(
    client: AsyncClient | HttpxAsyncClient,
) -> HttpxAsyncClient:
    if isinstance(client, HttpxAsyncClient):
        return client

    return client.http_client


def get_client(
    client: Client | HttpxClient,
) -> HttpxClient:
    if isinstance(client, HttpxClient):
        return client

    return client.http_client


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        return f"{value.isoformat()}Z"

    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _join_values(values: str | list[str] | list[int]) -> str:
    if isinstance(values, str):
        return values

    return ",".join([str(x) for x in values])


def process_params(
    uids: list[int] | None = None,
    index_uids: list[str] | None = None,
    statuses: str | list[str] | None = None,
    types: str | list[str] | None = None,
    before_enqueued_at: datetime | None = None,
    after_enqueued_at: datetime | None = None,
    before_started_at: datetime | None = None,
    after_finished_at: datetime | None = None,
    batch_uids: list[int] | None = None,
    canceled_by: list[int] | None = None,
    after_started_at: datetime | None = None,
    before_finished_at: datetime | None = None,
    limit: int | None = None,
    from_: int | str | None = None,
    reverse: bool | None = None,
) -> dict[str, str]:
    parameters = {}
    if uids is not None:
        parameters["uids"] = _join_values(uids)
    if batch_uids is not None:
        parameters["batchUids"] = _join_values(batch_uids)
    if index_uids is not None:
        parameters["indexUids"] = _join_values(index_uids)
    if canceled_by is not None:
        parameters["canceledBy"] = _join_values(canceled_by)
    if statuses is not None:
        parameters["statuses"] = _join_values(statuses)
    if types is not None:
        parameters["types"] = _join_values(types)
    if before_enqueued_at:
        parameters["beforeEnqueuedAt"] = _format_datetime(before_enqueued_at)
    if after_enqueued_at:
        parameters["afterEnqueuedAt"] = _format_datetime(after_enqueued_at)
    if before_started_at:
        parameters["beforeStartedAt"] = _format_datetime(before_started_at)
    if after_started_at:
        parameters["afterStartedAt"] = _format_datetime(after_started_at)
    if before_finished_at:
        parameters["beforeFinishedAt"] = _format_datetime(before_finished_at)
    if after_finished_at:
        parameters["afterFinishedAt"] = _format_datetime(after_finished_at)
    if limit is not None:
        parameters["limit"] = str(limit)
    if from_ is not None:
        parameters["from"] = str(from_)
    if reverse is not None:
        parameters["reverse"] = str(reverse).lower()

    return parameters


def _jwt_b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def encode_jwt(*, payload: JsonDict, key: str, json_handler: BuiltinHandler | OrjsonHandler) -> str:
    if not isinstance(payload, dict):
        raise TypeError("Expecting a dict object, as JWT only supports JSON objects as payloads.")

    payload = payload.copy()

    for time_claim in ("exp", "iat", "nbf"):
        if isinstance(payload.get(time_claim), datetime):
            payload[time_claim] = timegm(payload[time_claim].utctimetuple())

    if "iss" in payload and not isinstance(payload["iss"], str):
        raise TypeError("Issuer (iss) must be a string.")

    typ = "secevent+jwt" if "events" in payload else "JWT"
    header = _jwt_b64encode(json_handler.dump_bytes({"alg": "HS256", "typ": typ}))
    body = _jwt_b64encode(json_handler.dump_bytes(payload))
    message = f"{header}.{body}"
    sig = _jwt_b64encode(hmac.new(key.encode(), message.encode(), hashlib.sha256).digest())

    return f"{message}.{sig}"
