from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    pass

try:
    import orjson
except ImportError:  # pragma: nocover
    orjson = None  # type: ignore

try:
    import ujson
except ImportError:  # pragma: nocover
    ujson = None  # type: ignore


class _JsonHandler(ABC):
    @staticmethod
    @abstractmethod
    def dumps(obj: Any) -> str: ...

    @staticmethod
    @abstractmethod
    def loads(json_string: str | bytes | bytearray) -> Any: ...


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
    def dumps(obj: Any) -> str:
        return json.dumps(obj, cls=BuiltinHandler.serializer)

    @staticmethod
    def loads(json_string: str | bytes | bytearray) -> Any:
        return json.loads(json_string)


class OrjsonHandler(_JsonHandler):
    def __init__(self) -> None:
        if orjson is None:  # pragma: no cover
            raise ValueError("orjson must be installed to use the OrjsonHandler")

    @staticmethod
    def dumps(obj: Any) -> str:
        return orjson.dumps(obj).decode("utf-8")

    @staticmethod
    def loads(json_string: str | bytes | bytearray) -> Any:
        return orjson.loads(json_string)


class UjsonHandler(_JsonHandler):
    def __init__(self) -> None:
        if ujson is None:  # pragma: no cover
            raise ValueError("ujson must be installed to use the UjsonHandler")

    @staticmethod
    def dumps(obj: Any) -> str:
        return ujson.dumps(obj)

    @staticmethod
    def loads(json_string: str | bytes | bytearray) -> Any:
        return ujson.loads(json_string)
