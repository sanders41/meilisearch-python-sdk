from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any, Literal, TypeAlias

from meilisearch_python_sdk.json_handler import BuiltinHandler, OrjsonHandler

Filter: TypeAlias = str | list[str | list[str]]
JsonDict: TypeAlias = dict[str, Any]
JsonHandler: TypeAlias = BuiltinHandler | OrjsonHandler
JsonMapping: TypeAlias = MutableMapping[str, Any]
PluginEvent: TypeAlias = Literal["CONCURRENT_EVENT", "POST_EVENT", "PRE_EVENT"]
