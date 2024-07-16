from __future__ import annotations

import sys
from collections.abc import MutableMapping
from typing import Any

if sys.version_info >= (3, 10):  # pragma: no cover
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

Filter: TypeAlias = str | list[str | list[str]]
JsonDict: TypeAlias = dict[str, Any]
JsonMapping: TypeAlias = MutableMapping[str, Any]
