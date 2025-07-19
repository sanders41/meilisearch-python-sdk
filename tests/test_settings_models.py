import pytest

from meilisearch_python_sdk.models.settings import RestEmbedder


def test_index_settings_with_document_template_error():
    with pytest.raises(ValueError) as e:
        RestEmbedder(
            url="https://test.com",
            dimensions=128,
            document_template="test",
            request={"test": "test"},
            response={"test": "test"},
            indexing_fragments={"test": "test"},
        )

    assert "document_template must be None when indexing_fragments is set" in str(e.value)
