import json

import pytest

from meilisearch_python_sdk.json_handler import BuiltinHandler, OrjsonHandler


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_dumps(json_handler):
    result = json_handler.dumps({"id": 1, "title": "Shazam!"})

    assert isinstance(result, str)
    assert json.loads(result) == {"id": 1, "title": "Shazam!"}
