from __future__ import annotations

import base64
import hashlib
import hmac
import sys
from calendar import timegm
from datetime import datetime, timezone
from functools import lru_cache
from typing import TYPE_CHECKING

from httpx2 import AsyncClient as HttpxAsyncClient
from httpx2 import Client as HttpxClient

from meilisearch_python_sdk.errors import (
    DecodeError,
    ExpiredSignatureError,
    ImmatureSignatureError,
    InvalidIssuedAtError,
    InvalidJTIError,
    InvalidSignatureError,
    InvalidSubjectError,
)
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


@lru_cache(maxsize=1)
def use_task_groups() -> bool:
    return True if sys.version_info >= (3, 11) else False


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


def decode_jwt(
    *, token: str, key: str, json_handler: BuiltinHandler | OrjsonHandler, leeway: float = 0
) -> JsonDict:
    header_b64, payload_b64, sig_b64 = token.split(".")
    message = f"{header_b64}.{payload_b64}"
    expected = _jwt_b64encode(hmac.new(key.encode(), message.encode(), hashlib.sha256).digest())

    if not hmac.compare_digest(sig_b64, expected):
        raise InvalidSignatureError("Signature verification failed")

    padding = "=" * (4 - len(payload_b64) % 4)

    try:
        payload = json_handler.loads(base64.urlsafe_b64decode(payload_b64 + padding))
    except Exception as e:
        raise DecodeError(f"Invalid payload string: {e}") from e

    if not isinstance(payload, dict):
        raise DecodeError("Invalid payload string: must be a json object")

    now = datetime.now(tz=timezone.utc).timestamp()

    if "iat" in payload:
        try:
            iat = int(payload["iat"])
        except (ValueError, TypeError):
            raise InvalidIssuedAtError("Issued At claim (iat) must be an integer.") from None

        if iat > (now + leeway):
            raise ImmatureSignatureError("The token is not yet valid (iat)")

    if "nbf" in payload:
        try:
            nbf = int(payload["nbf"])
        except (ValueError, TypeError):
            raise DecodeError("Not Before claim (nbf) must be an integer.") from None

        if nbf > (now + leeway):
            raise ImmatureSignatureError("The token is not yet valid (nbf)")

    if "exp" in payload:
        try:
            exp = int(payload["exp"])
        except (ValueError, TypeError):
            raise DecodeError("Expiration Time claim (exp) must be an integer.") from None

        if exp <= (now - leeway):
            raise ExpiredSignatureError("Signature has expired")

    if "sub" in payload and not isinstance(payload["sub"], str):
        raise InvalidSubjectError("Subject must be a string")

    if "jti" in payload and not isinstance(payload["jti"], str):
        raise InvalidJTIError("JWT ID must be a string")

    return payload
