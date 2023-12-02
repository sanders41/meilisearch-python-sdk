from collections.abc import Mapping
from typing import Any, Dict, List, Union

Filter = Union[str, List[Union[str, List[str]]]]
JsonDict = Dict[str, Any]
JsonMapping = Mapping[str, Any]
