import base64
import hashlib
import hmac
from calendar import timegm
from datetime import datetime, timezone

import pytest

from meilisearch_python_sdk._utils import decode_jwt, encode_jwt
from meilisearch_python_sdk.errors import (
    DecodeError,
    ExpiredSignatureError,
    ImmatureSignatureError,
    InvalidIssuedAtError,
    InvalidJTIError,
    InvalidSubjectError,
)
from meilisearch_python_sdk.json_handler import BuiltinHandler, OrjsonHandler


def make_raw_token(payload_bytes, key, json_handler):
    """Build a signed token with arbitrary raw payload bytes (for testing invalid payloads)."""
    header_b64 = (
        base64.urlsafe_b64encode(json_handler.dump_bytes({"alg": "HS256", "typ": "JWT"}))
        .rstrip(b"=")
        .decode()
    )
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode()
    message = f"{header_b64}.{payload_b64}"
    sig = (
        base64.urlsafe_b64encode(hmac.new(key.encode(), message.encode(), hashlib.sha256).digest())
        .rstrip(b"=")
        .decode()
    )
    return f"{message}.{sig}"


def utc_timestamp():
    return timegm(datetime.now(tz=timezone.utc).utctimetuple())


def payload():
    return {"iss": "jeff", "exp": utc_timestamp() + 15, "claim": "insanity"}


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_encode_decode(json_handler):
    utc_timestamp = timegm(datetime.now(tz=timezone.utc).utctimetuple())
    payload = {"iss": "jeff", "exp": utc_timestamp + 15, "claim": "insanity"}

    secret = "secret"
    jwt_message = encode_jwt(payload=payload, key=secret, json_handler=json_handler)
    decoded_payload = decode_jwt(token=jwt_message, key=secret, json_handler=json_handler)

    assert decoded_payload == payload


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
@pytest.mark.parametrize("types", ("string", tuple(), list(), 42, set()))
def test_encode_bad_type(types, json_handler):
    with pytest.raises(TypeError):
        encode_jwt(payload=types, key="secret", json_handler=json_handler)


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_encode_with_non_str_iss(json_handler):
    with pytest.raises(TypeError):
        encode_jwt(
            payload={
                "iss": 123,
            },
            key="secret",
            json_handler=json_handler,
        )


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_encode_with_typo(json_handler):
    payload = {
        "iss": "https://scim.example.com",
        "iat": 1458496404,
        "jti": "4d3559ec67504aaba65d40b0363faad8",
        "aud": [
            "https://scim.example.com/Feeds/98d52461fa5bbc879593b7754",
            "https://scim.example.com/Feeds/5d7604516b1d08641d7676ee7",
        ],
        "events": {
            "urn:ietf:params:scim:event:create": {
                "ref": "https://scim.example.com/Users/44f6142df96bd6ab61e7521d9",
                "attributes": ["id", "name", "userName", "password", "emails"],
            }
        },
    }
    token = encode_jwt(payload=payload, key="secret", json_handler=json_handler)
    header_b64 = token[0 : token.index(".")]
    input_bytes = header_b64.encode("utf-8")
    rem = len(input_bytes) % 4

    if rem > 0:
        input_bytes += b"=" * (4 - rem)

    header = base64.urlsafe_b64decode(input_bytes)
    header_obj = json_handler.loads(header)

    assert "typ" in header_obj
    assert header_obj["typ"] == "secevent+jwt"


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_encode_datetime(json_handler):
    secret = "secret"
    current_datetime = datetime.now(tz=timezone.utc)
    payload = {
        "exp": current_datetime,
        "iat": current_datetime,
        "nbf": current_datetime,
    }
    jwt_message = encode_jwt(payload=payload, key=secret, json_handler=json_handler)
    decoded_payload = decode_jwt(token=jwt_message, key=secret, json_handler=json_handler, leeway=1)

    assert decoded_payload["exp"] == timegm(current_datetime.utctimetuple())
    assert decoded_payload["iat"] == timegm(current_datetime.utctimetuple())
    assert decoded_payload["nbf"] == timegm(current_datetime.utctimetuple())
    assert payload == {
        "exp": current_datetime,
        "iat": current_datetime,
        "nbf": current_datetime,
    }


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_encode_decode_sub_claim(json_handler):
    payload = {"sub": "user123"}
    secret = "your-256-bit-secret"
    token = encode_jwt(payload=payload, key=secret, json_handler=json_handler)
    decoded = decode_jwt(token=token, key=secret, json_handler=json_handler)
    assert decoded["sub"] == "user123"


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_encode_decode_with_valid_jti_claim(json_handler):
    payload = {"jti": "unique-id-456"}
    secret = "your-256-bit-secret"
    token = encode_jwt(payload=payload, key=secret, json_handler=json_handler)
    decoded = decode_jwt(token=token, key=secret, json_handler=json_handler)
    assert decoded["jti"] == "unique-id-456"


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_decode_invalid_payload_string(json_handler):
    example_jwt = make_raw_token(b"hello world", "secret", json_handler)
    with pytest.raises(DecodeError) as exc:
        decode_jwt(token=example_jwt, key="secret", json_handler=json_handler)
    assert "Invalid payload string" in str(exc.value)


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_decode_with_non_mapping_payload(json_handler):
    example_jwt = make_raw_token(b"1", "secret", json_handler)
    with pytest.raises(DecodeError) as context:
        decode_jwt(token=example_jwt, key="secret", json_handler=json_handler)
    assert str(context.value) == "Invalid payload string: must be a json object"


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_decode_raises_exception_if_exp_is_not_int(json_handler):
    token = encode_jwt(payload={"exp": "not-an-int"}, key="secret", json_handler=json_handler)
    with pytest.raises(DecodeError) as exc:
        decode_jwt(token=token, key="secret", json_handler=json_handler)
    assert "exp" in str(exc.value)


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_decode_raises_exception_if_iat_is_not_int(json_handler):
    token = encode_jwt(payload={"iat": "not-an-int"}, key="secret", json_handler=json_handler)
    with pytest.raises(InvalidIssuedAtError):
        decode_jwt(token=token, key="secret", json_handler=json_handler)


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_decode_raises_exception_if_iat_is_greater_than_now(json_handler):
    p = {
        "iss": "jeff",
        "exp": utc_timestamp() + 15,
        "claim": "insanity",
        "iat": utc_timestamp() + 10,
    }
    secret = "secret"
    jwt_message = encode_jwt(payload=p, key=secret, json_handler=json_handler)
    with pytest.raises(ImmatureSignatureError):
        decode_jwt(token=jwt_message, key=secret, json_handler=json_handler)


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_decode_works_if_iat_is_str_of_a_number(json_handler):
    p = {"iat": "1638202770"}
    secret = "secret"
    jwt_message = encode_jwt(payload=p, key=secret, json_handler=json_handler)
    data = decode_jwt(token=jwt_message, key=secret, json_handler=json_handler)
    assert data["iat"] == "1638202770"


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_decode_raises_exception_if_nbf_is_not_int(json_handler):
    token = encode_jwt(payload={"nbf": "not-an-int"}, key="secret", json_handler=json_handler)
    with pytest.raises(DecodeError):
        decode_jwt(token=token, key="secret", json_handler=json_handler)


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_decode_with_expiration(json_handler):
    p = {"exp": utc_timestamp() - 1}
    secret = "secret"
    jwt_message = encode_jwt(payload=p, key=secret, json_handler=json_handler)
    with pytest.raises(ExpiredSignatureError):
        decode_jwt(token=jwt_message, key=secret, json_handler=json_handler)


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_decode_with_notbefore(json_handler):
    p = {"nbf": utc_timestamp() + 10}
    secret = "secret"
    jwt_message = encode_jwt(payload=p, key=secret, json_handler=json_handler)
    with pytest.raises(ImmatureSignatureError):
        decode_jwt(token=jwt_message, key=secret, json_handler=json_handler)


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_decode_invalid_int_sub_claim(json_handler):
    payload = {"sub": 1224344}
    secret = "your-256-bit-secret"
    token = encode_jwt(payload=payload, key=secret, json_handler=json_handler)
    with pytest.raises(InvalidSubjectError):
        decode_jwt(token=token, key=secret, json_handler=json_handler)


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_jti_claim_with_invalid_int_value(json_handler):
    payload = {"jti": 12223}
    secret = "your-256-bit-secret"
    token = encode_jwt(payload=payload, key=secret, json_handler=json_handler)
    with pytest.raises(InvalidJTIError):
        decode_jwt(token=token, key=secret, json_handler=json_handler)
