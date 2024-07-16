import sys
from collections.abc import MutableMapping
from typing import Any, Dict, List, Union

if sys.version_info >= (3, 10):  # pragma: no cover
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

Filter: TypeAlias = Union[str, List[Union[str, List[str]]]]
JsonDict: TypeAlias = Dict[str, Any]
JsonMapping: TypeAlias = MutableMapping[str, Any]
