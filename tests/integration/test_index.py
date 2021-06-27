from datetime import datetime

import pytest
from httpx import Response

from meilisearch_python_async._http_requests import _HttpRequests
from meilisearch_python_async.errors import MeiliSearchApiError, MeiliSearchTimeoutError
from meilisearch_python_async.index import Index
from meilisearch_python_async.models import MeiliSearchSettings


@pytest.fixture
def new_settings():
    return MeiliSearchSettings(
        ranking_rules=["typo", "words"], searchable_attributes=["title", "overview"]
    )


@pytest.fixture
def default_ranking_rules():
    return ["typo", "words", "proximity", "attribute", "wordsPosition", "exactness"]


@pytest.fixture
def new_ranking_rules():
    return ["typo", "exactness"]


@pytest.fixture
def new_distinct_attribute():
    return "title"


@pytest.fixture
def default_distinct_attribute():
    return None


@pytest.fixture
def new_searchable_attributes():
    return ["something", "random"]


@pytest.fixture
def displayed_attributes():
    return ["id", "release_date", "title", "poster", "overview", "genre"]


@pytest.fixture
def new_stop_words():
    return ["of", "the"]


@pytest.fixture
def new_synonyms():
    return {"hp": ["harry potter"]}


@pytest.fixture
def attributes_for_faceting():
    return ["title", "release_date"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("indexes_sample")
async def test_delete_index(test_client, index_uid, index_uid2):
    response = await test_client.index(uid=index_uid).delete()
    assert response == 204

    with pytest.raises(MeiliSearchApiError):
        await test_client.get_index(uid=index_uid)

    response = await test_client.index(uid=index_uid2).delete()
    assert response == 204

    with pytest.raises(MeiliSearchApiError):
        await test_client.get_index(uid=index_uid2)

    indexes = await test_client.get_indexes()
    assert indexes is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("indexes_sample")
async def test_update_index(test_client, index_uid):
    index = test_client.index(uid=index_uid)
    await index.update(primary_key="objectID")

    assert index.primary_key == "objectID"
    assert await index.get_primary_key() == "objectID"


@pytest.mark.asyncio
async def test_get_all_update_status_default(empty_index):
    index = await empty_index()
    response = await index.get_all_update_status()

    assert response is None


@pytest.mark.asyncio
async def test_get_all_update_status(empty_index, small_movies):
    index = await empty_index()
    response = await index.add_documents(small_movies)
    response = await index.add_documents(small_movies)
    response = await index.get_all_update_status()
    assert len(response) == 2


@pytest.mark.asyncio
async def test_wait_for_pending_update(empty_index, small_movies):
    index = await empty_index()
    response = await index.add_documents(small_movies)
    update = await index.wait_for_pending_update(response.update_id)
    assert update.status == "processed"


@pytest.mark.asyncio
async def test_wait_for_pending_update_time_out(empty_index, small_movies):
    with pytest.raises(MeiliSearchTimeoutError):
        index = await empty_index()
        response = await index.add_documents(small_movies)
        await index.wait_for_pending_update(response.update_id, timeout_in_ms=1, interval_in_ms=1)


@pytest.mark.asyncio
async def test_get_stats(empty_index, small_movies):
    index = await empty_index()
    update = await index.add_documents(small_movies)
    await index.wait_for_pending_update(update.update_id)
    response = await index.get_stats()

    assert response.number_of_documents == 30


@pytest.mark.asyncio
async def test_get_settings_default(empty_index, default_ranking_rules):
    index = await empty_index()
    response = await index.get_settings()
    assert sorted(response.ranking_rules) == sorted(default_ranking_rules)
    assert response.distinct_attribute is None
    assert response.searchable_attributes == ["*"]
    assert response.displayed_attributes == ["*"]
    assert response.stop_words == []
    assert response.synonyms == {}


@pytest.mark.asyncio
async def test_update_settings(empty_index, new_settings):
    index = await empty_index()
    response = await index.update_settings(new_settings)
    update = await index.wait_for_pending_update(response.update_id)
    assert update.status == "processed"
    response = await index.get_settings()
    assert sorted(response.ranking_rules) == sorted(new_settings.ranking_rules)
    assert response.distinct_attribute is None
    assert sorted(response.searchable_attributes) == sorted(new_settings.searchable_attributes)
    assert response.displayed_attributes == ["*"]
    assert response.stop_words == []
    assert response.synonyms == {}


@pytest.mark.asyncio
async def test_reset_settings(empty_index, new_settings, default_ranking_rules):
    index = await empty_index()
    response = await index.update_settings(new_settings)
    update = await index.wait_for_pending_update(response.update_id)
    assert update.status == "processed"
    response = await index.get_settings()
    assert sorted(response.ranking_rules) == sorted(new_settings.ranking_rules)
    assert response.distinct_attribute is None
    assert sorted(response.searchable_attributes) == sorted(new_settings.searchable_attributes)
    assert response.displayed_attributes == ["*"]
    assert response.stop_words == []
    assert response.synonyms == {}
    response = await index.reset_settings()
    update = await index.wait_for_pending_update(response.update_id)
    assert update.status == "processed"
    response = await index.get_settings()
    assert sorted(response.ranking_rules) == sorted(default_ranking_rules)
    assert response.distinct_attribute is None
    assert response.displayed_attributes == ["*"]
    assert response.searchable_attributes == ["*"]
    assert response.stop_words == []
    assert response.synonyms == {}


@pytest.mark.asyncio
async def test_get_ranking_rules_default(empty_index, default_ranking_rules):
    index = await empty_index()
    response = await index.get_ranking_rules()
    assert sorted(response) == sorted(default_ranking_rules)


@pytest.mark.asyncio
async def test_update_ranking_rules(empty_index, new_ranking_rules):
    index = await empty_index()
    response = await index.update_ranking_rules(new_ranking_rules)
    await index.wait_for_pending_update(response.update_id)
    response = await index.get_ranking_rules()
    assert sorted(response) == sorted(new_ranking_rules)


@pytest.mark.asyncio
async def test_reset_ranking_rules(empty_index, new_ranking_rules, default_ranking_rules):
    index = await empty_index()
    response = await index.update_ranking_rules(new_ranking_rules)
    await index.wait_for_pending_update(response.update_id)
    response = await index.get_ranking_rules()
    assert sorted(response) == sorted(new_ranking_rules)
    response = await index.reset_ranking_rules()
    await index.wait_for_pending_update(response.update_id)
    response = await index.get_ranking_rules()
    assert sorted(response) == sorted(default_ranking_rules)


@pytest.mark.asyncio
async def test_get_distinct_attribute(empty_index, default_distinct_attribute):
    index = await empty_index()
    response = await index.get_distinct_attribute()
    assert response == default_distinct_attribute


@pytest.mark.asyncio
async def test_update_distinct_attribute(empty_index, new_distinct_attribute):
    index = await empty_index()
    response = await index.update_distinct_attribute(new_distinct_attribute)
    await index.wait_for_pending_update(response.update_id)
    response = await index.get_distinct_attribute()
    assert response == new_distinct_attribute


@pytest.mark.asyncio
async def test_reset_distinct_attribute(
    empty_index, new_distinct_attribute, default_distinct_attribute
):
    index = await empty_index()
    response = await index.update_distinct_attribute(new_distinct_attribute)
    update = await index.wait_for_pending_update(response.update_id)
    assert update.status == "processed"
    response = await index.get_distinct_attribute()
    assert response == new_distinct_attribute
    response = await index.reset_distinct_attribute()
    await index.wait_for_pending_update(response.update_id)
    response = await index.get_distinct_attribute()
    assert response == default_distinct_attribute


@pytest.mark.asyncio
async def test_get_searchable_attributes(empty_index, small_movies):
    index = await empty_index()
    response = await index.get_searchable_attributes()
    assert response == ["*"]
    response = await index.add_documents(small_movies, primary_key="id")
    await index.wait_for_pending_update(response.update_id)
    get_attributes = await index.get_searchable_attributes()
    assert get_attributes == ["*"]


@pytest.mark.asyncio
async def test_update_searchable_attributes(empty_index, new_searchable_attributes):
    index = await empty_index()
    response = await index.update_searchable_attributes(new_searchable_attributes)
    await index.wait_for_pending_update(response.update_id)
    response = await index.get_searchable_attributes()
    assert sorted(response) == sorted(new_searchable_attributes)


@pytest.mark.asyncio
async def test_reset_searchable_attributes(empty_index, new_searchable_attributes):
    index = await empty_index()
    response = await index.update_searchable_attributes(new_searchable_attributes)
    update = await index.wait_for_pending_update(response.update_id)
    assert update.status == "processed"
    response = await index.get_searchable_attributes()
    assert sorted(response) == sorted(new_searchable_attributes)
    response = await index.reset_searchable_attributes()
    await index.wait_for_pending_update(response.update_id)
    response = await index.get_searchable_attributes()
    assert response == ["*"]


@pytest.mark.asyncio
async def test_get_displayed_attributes(empty_index, small_movies):
    index = await empty_index()
    response = await index.get_displayed_attributes()
    assert response == ["*"]
    response = await index.add_documents(small_movies)
    await index.wait_for_pending_update(response.update_id)
    get_attributes = await index.get_displayed_attributes()
    assert get_attributes == ["*"]


@pytest.mark.asyncio
async def test_update_displayed_attributes(empty_index, displayed_attributes):
    index = await empty_index()
    response = await index.update_displayed_attributes(displayed_attributes)
    await index.wait_for_pending_update(response.update_id)
    response = await index.get_displayed_attributes()
    assert sorted(response) == sorted(displayed_attributes)


@pytest.mark.asyncio
async def test_reset_displayed_attributes(empty_index, displayed_attributes):
    index = await empty_index()
    response = await index.update_displayed_attributes(displayed_attributes)
    update = await index.wait_for_pending_update(response.update_id)
    assert update.status == "processed"
    response = await index.get_displayed_attributes()
    assert sorted(response) == sorted(displayed_attributes)
    response = await index.reset_displayed_attributes()
    await index.wait_for_pending_update(response.update_id)
    response = await index.get_displayed_attributes()
    assert response == ["*"]


@pytest.mark.asyncio
async def test_get_stop_words_default(empty_index):
    index = await empty_index()
    response = await index.get_stop_words()
    assert response is None


@pytest.mark.asyncio
async def test_update_stop_words(empty_index, new_stop_words):
    index = await empty_index()
    response = await index.update_stop_words(new_stop_words)
    update = await index.wait_for_pending_update(response.update_id)
    assert update.status == "processed"
    response = await index.get_stop_words()
    assert sorted(response) == sorted(new_stop_words)


@pytest.mark.asyncio
async def test_reset_stop_words(empty_index, new_stop_words):
    index = await empty_index()
    response = await index.update_stop_words(new_stop_words)
    update = await index.wait_for_pending_update(response.update_id)
    assert update.status == "processed"
    response = await index.get_stop_words()
    assert sorted(response) == sorted(new_stop_words)
    response = await index.reset_stop_words()
    update = await index.wait_for_pending_update(response.update_id)
    assert update.status == "processed"
    response = await index.get_stop_words()
    assert response is None


@pytest.mark.asyncio
async def test_get_synonyms_default(empty_index):
    index = await empty_index()
    response = await index.get_synonyms()
    assert response is None


@pytest.mark.asyncio
async def test_update_synonyms(empty_index, new_synonyms):
    index = await empty_index()
    response = await index.update_synonyms(new_synonyms)
    update = await index.wait_for_pending_update(response.update_id)
    assert update.status == "processed"
    response = await index.get_synonyms()
    assert response == new_synonyms


@pytest.mark.asyncio
async def test_reset_synonyms(empty_index, new_synonyms):
    index = await empty_index()
    response = await index.update_synonyms(new_synonyms)
    update = await index.wait_for_pending_update(response.update_id)
    assert update.status == "processed"
    response = await index.get_synonyms()
    assert response == new_synonyms
    response = await index.reset_synonyms()
    update = await index.wait_for_pending_update(response.update_id)
    assert update.status == "processed"
    response = await index.get_synonyms()
    assert response is None


@pytest.mark.asyncio
async def test_get_attributes_for_faceting(empty_index):
    index = await empty_index()
    response = await index.get_attributes_for_faceting()
    assert response is None


@pytest.mark.asyncio
async def test_update_attributes_for_faceting(empty_index, attributes_for_faceting):
    index = await empty_index()
    response = await index.update_attributes_for_faceting(attributes_for_faceting)
    await index.wait_for_pending_update(response.update_id)
    response = await index.get_attributes_for_faceting()
    assert sorted(response) == sorted(attributes_for_faceting)


@pytest.mark.asyncio
async def test_reset_attributes_for_faceting(empty_index, attributes_for_faceting):
    index = await empty_index()
    response = await index.update_attributes_for_faceting(attributes_for_faceting)
    update = await index.wait_for_pending_update(response.update_id)
    assert update.status == "processed"
    response = await index.get_attributes_for_faceting()
    assert sorted(response) == sorted(attributes_for_faceting)
    response = await index.reset_attributes_for_faceting()
    await index.wait_for_pending_update(response.update_id)
    response = await index.get_attributes_for_faceting()
    assert response is None


@pytest.mark.parametrize(
    "iso_date, expected",
    [
        ("2021-05-11T03:12:22.563960100Z", datetime(2021, 5, 11, 3, 12, 22, 563960)),
        (datetime(2021, 5, 11, 3, 12, 22, 563960), datetime(2021, 5, 11, 3, 12, 22, 563960)),
        (None, None),
    ],
)
def test_iso_to_date_time(iso_date, expected, test_client):
    index = Index(test_client, "test")
    converted = index._iso_to_date_time(iso_date)

    assert converted == expected


@pytest.mark.asyncio
async def test_str(empty_index):
    index = await empty_index()
    got = index.__str__()

    assert "uid" in got
    assert "primary_key" in got
    assert "created_at" in got
    assert "updated_at" in got


@pytest.mark.asyncio
async def test_repr(empty_index):
    index = await empty_index()
    got = index.__repr__()

    assert "uid" in got
    assert "primary_key" in got
    assert "created_at" in got
    assert "updated_at" in got


@pytest.mark.asyncio
@pytest.mark.usefixtures("indexes_sample")
async def test_delete_if_exists(test_client, index_uid):
    assert await test_client.get_index(uid=index_uid)
    deleted = await test_client.index(index_uid).delete_if_exists()
    assert deleted is True
    with pytest.raises(MeiliSearchApiError):
        await test_client.get_index(uid=index_uid)


@pytest.mark.asyncio
async def test_delete_if_exists_no_delete(test_client):
    with pytest.raises(MeiliSearchApiError):
        await test_client.get_index(uid="none")

    deleted = await test_client.index("none").delete_if_exists()
    assert deleted is False


@pytest.mark.asyncio
@pytest.mark.usefixtures("indexes_sample")
async def test_delete_if_exists_error(test_client, index_uid, monkeypatch):
    async def mock_response(*args, **kwargs):
        raise MeiliSearchApiError("test", Response(status_code=404))

    monkeypatch.setattr(_HttpRequests, "_send_request", mock_response)
    with pytest.raises(MeiliSearchApiError):
        await test_client.index(index_uid).delete_if_exists()


@pytest.mark.asyncio
@pytest.mark.usefixtures("indexes_sample")
async def test_delete_index_if_exists(test_client, index_uid):
    assert await test_client.get_index(uid=index_uid)
    deleted = await test_client.delete_index_if_exists(index_uid)
    assert deleted is True
    with pytest.raises(MeiliSearchApiError):
        await test_client.get_index(uid=index_uid)


@pytest.mark.asyncio
async def test_delete_index_if_exists_no_delete(test_client):
    with pytest.raises(MeiliSearchApiError):
        await test_client.get_index(uid="none")

    deleted = await test_client.delete_index_if_exists("none")
    assert deleted is False


@pytest.mark.asyncio
@pytest.mark.usefixtures("indexes_sample")
async def test_delete_index_if_exists_error(test_client, index_uid, monkeypatch):
    async def mock_response(*args, **kwargs):
        raise MeiliSearchApiError("test", Response(status_code=404))

    monkeypatch.setattr(_HttpRequests, "_send_request", mock_response)
    with pytest.raises(MeiliSearchApiError):
        await test_client.delete_index_if_exists(index_uid)
