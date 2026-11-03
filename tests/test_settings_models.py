import pytest

from meilisearch_python_sdk.models.settings import (
    CompositeEmbedder,
    HuggingFaceEmbedder,
    MeilisearchSettings,
    OllamaEmbedder,
    OpenAiEmbedder,
    RestEmbedder,
    UserProvidedEmbedder,
)


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


@pytest.mark.parametrize(
    "embedder, expected",
    (
        ({"source": "openAi"}, OpenAiEmbedder),
        ({"source": "huggingFace"}, HuggingFaceEmbedder),
        ({"source": "ollama", "model": "test"}, OllamaEmbedder),
        (
            {
                "source": "rest",
                "url": "https://test.com",
                "dimensions": 1,
                "request": {},
                "response": {},
            },
            RestEmbedder,
        ),
        ({"source": "userProvided", "dimensions": 1}, UserProvidedEmbedder),
        (
            {
                "source": "composite",
                "searchEmbedder": {"source": "ollama", "model": "test"},
                "indexingEmbedder": {"source": "huggingFace"},
            },
            CompositeEmbedder,
        ),
    ),
)
def test_embedder_source_selects_model(embedder, expected):
    settings = MeilisearchSettings.model_validate({"embedders": {"default": embedder}})

    assert settings.embedders is not None
    assert type(settings.embedders["default"]) is expected
