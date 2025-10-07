from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any, TypeAlias

Filter: TypeAlias = str | list[str | list[str]]
JsonDict: TypeAlias = dict[str, Any]
JsonMapping: TypeAlias = MutableMapping[str, Any]
