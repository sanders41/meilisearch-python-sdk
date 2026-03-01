from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any, Literal, TypeAlias

Filter: TypeAlias = str | list[str | list[str]]
JsonDict: TypeAlias = dict[str, Any]
JsonMapping: TypeAlias = MutableMapping[str, Any]
PluginEvent: TypeAlias = Literal["CONCURRENT_EVENT", "POST_EVENT", "PRE_EVENT"]
