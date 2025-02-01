from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING, Any, Union

if TYPE_CHECKING:  # pragma: no cover
    import sys

    if sys.version_info >= (3, 10):
        from typing import TypeAlias
    else:
        from typing_extensions import TypeAlias

Filter: TypeAlias = Union[str, list[Union[str, list[str]]]]
JsonDict: TypeAlias = dict[str, Any]
JsonMapping: TypeAlias = MutableMapping[str, Any]
