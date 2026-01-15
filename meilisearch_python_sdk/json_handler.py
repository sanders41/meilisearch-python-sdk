from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

try:
    import orjson
except ImportError:  # pragma: no cover
    orjson = None  # type: ignore


class _JsonHandler(ABC):
    @staticmethod
    @abstractmethod
    def dumps(obj: Any) -> str: ...  # noqa: ANN401

    @staticmethod
    @abstractmethod
    def dump_bytes(obj: Any) -> bytes: ...  # noqa: ANN401

    @staticmethod
    @abstractmethod
    def loads(json_string: str | bytes | bytearray) -> Any: ...  # noqa: ANN401


class BuiltinHandler(_JsonHandler):
    serializer: type[json.JSONEncoder] | None = None

    def __init__(self, serializer: type[json.JSONEncoder] | None = None) -> None:
        """Uses the json module from the Python standard library.

        Args:
            serializer: A custom JSONEncode to handle serializing fields that the build in
                json.dumps cannot handle, for example UUID and datetime. Defaults to None.
        """
        BuiltinHandler.serializer = serializer

    @staticmethod
    def dumps(obj: Any) -> str:  # noqa: ANN401
        return json.dumps(obj, cls=BuiltinHandler.serializer)

    @staticmethod
    def dump_bytes(obj: Any) -> bytes:  # noqa: ANN401
        return json.dumps(obj, cls=BuiltinHandler.serializer).encode("utf-8")

    @staticmethod
    def loads(json_string: str | bytes | bytearray) -> Any:  # noqa: ANN401
        return json.loads(json_string)


class OrjsonHandler(_JsonHandler):
    def __init__(self) -> None:
        if orjson is None:  # pragma: no cover
            raise ValueError("orjson must be installed to use the OrjsonHandler")

    @staticmethod
    def dumps(obj: Any) -> str:  # noqa: ANN401
        return orjson.dumps(obj).decode("utf-8")

    @staticmethod
    def dump_bytes(obj: Any) -> bytes:  # noqa: ANN401
        return orjson.dumps(obj)

    @staticmethod
    def loads(json_string: str | bytes | bytearray) -> Any:  # noqa: ANN401
        return orjson.loads(json_string)
