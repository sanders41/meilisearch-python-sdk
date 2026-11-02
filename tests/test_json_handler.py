import json
from uuid import UUID, uuid4

import pytest

from meilisearch_python_sdk.json_handler import BuiltinHandler, OrjsonHandler


@pytest.mark.parametrize("json_handler", (BuiltinHandler(), OrjsonHandler()))
def test_dumps(json_handler):
    result = json_handler.dumps({"id": 1, "title": "Shazam!"})

    assert isinstance(result, str)
    assert json.loads(result) == {"id": 1, "title": "Shazam!"}


def test_serializer_not_shared():
    doc_id = uuid4()

    class UUIDEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, UUID):
                return str(o)
            return super().default(o)

    handler = BuiltinHandler(serializer=UUIDEncoder)
    BuiltinHandler()

    assert json.loads(
        handler.dumps(
            {
                "id": doc_id,
            }
        )
    ) == {"id": str(doc_id)}
    assert json.loads(handler.dump_bytes({"id": doc_id})) == {"id": str(doc_id)}
