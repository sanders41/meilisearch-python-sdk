import pytest
from httpx import Response

from meilisearch_python_sdk._http_requests import HttpRequests
from meilisearch_python_sdk._task import wait_for_task
from meilisearch_python_sdk.errors import MeilisearchApiError
from meilisearch_python_sdk.models.settings import (
    Faceting,
    MinWordSizeForTypos,
    Pagination,
    ProximityPrecision,
    TypoTolerance,
)


@pytest.fixture
def default_ranking_rules():
    return ["words", "typo", "proximity", "attribute", "sort", "exactness"]


@pytest.fixture
def default_faceting():
    return Faceting(max_values_per_facet=100, sort_facet_values_by={"*": "alpha"})


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
def filterable_attributes():
    return ["release_date", "title"]


@pytest.fixture
def default_pagination():
    return Pagination(max_total_hits=1000)


@pytest.fixture
def sortable_attributes():
    return ["genre", "title"]


@pytest.mark.usefixtures("indexes_sample")
def test_delete_index(client, index_uid, index_uid2):
    response = client.index(uid=index_uid).delete()
    wait_for_task(client, response.task_uid)

    with pytest.raises(MeilisearchApiError):
        client.get_index(uid=index_uid)

    response = client.index(uid=index_uid2).delete()
    wait_for_task(client, response.task_uid)

    with pytest.raises(MeilisearchApiError):
        client.get_index(uid=index_uid2)

    indexes = client.get_indexes()
    assert indexes is None


@pytest.mark.usefixtures("indexes_sample")
def test_update_index(client, index_uid):
    index = client.index(uid=index_uid)
    index.update(primary_key="objectID")

    assert index.primary_key == "objectID"
    assert index.get_primary_key() == "objectID"


def test_get_stats(empty_index, small_movies):
    index = empty_index()
    update = index.add_documents(small_movies)
    wait_for_task(index.http_client, update.task_uid)
    response = index.get_stats()

    assert response.number_of_documents == 30


def test_get_settings_default(
    empty_index, default_ranking_rules, default_faceting, default_pagination
):
    index = empty_index()
    response = index.get_settings()
    assert response.ranking_rules == default_ranking_rules
    assert response.distinct_attribute is None
    assert response.searchable_attributes == ["*"]
    assert response.displayed_attributes == ["*"]
    assert response.stop_words == []
    assert response.synonyms == {}
    assert response.sortable_attributes == []
    assert response.typo_tolerance.enabled is True
    assert response.faceting == default_faceting
    assert response.pagination == default_pagination
    assert response.proximity_precision is None
    assert response.separator_tokens == []
    assert response.non_separator_tokens == []
    assert response.dictionary == []


def test_update_settings(empty_index, new_settings):
    index = empty_index()
    response = index.update_settings(new_settings)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_settings()
    assert response.ranking_rules == new_settings.ranking_rules
    assert response.distinct_attribute is None
    assert response.searchable_attributes == new_settings.searchable_attributes
    assert response.displayed_attributes == ["*"]
    assert response.stop_words == []
    assert response.synonyms == {}
    assert response.sortable_attributes == new_settings.sortable_attributes
    assert response.typo_tolerance.enabled is False
    assert (
        response.faceting.max_values_per_facet == new_settings.faceting.max_values_per_facet == 123
    )
    assert response.pagination == new_settings.pagination
    assert response.proximity_precision == new_settings.proximity_precision
    assert response.separator_tokens == new_settings.separator_tokens
    assert response.non_separator_tokens == new_settings.non_separator_tokens
    assert response.dictionary == new_settings.dictionary


def test_reset_settings(empty_index, new_settings, default_ranking_rules):
    index = empty_index()
    response = index.update_settings(new_settings)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_settings()
    assert response.ranking_rules == new_settings.ranking_rules
    assert response.distinct_attribute is None
    assert response.searchable_attributes == new_settings.searchable_attributes
    assert response.displayed_attributes == ["*"]
    assert response.stop_words == []
    assert response.synonyms == {}
    assert response.sortable_attributes == new_settings.sortable_attributes
    assert response.typo_tolerance.enabled is False
    assert response.pagination == new_settings.pagination
    assert response.proximity_precision == new_settings.proximity_precision
    response = index.reset_settings()
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_settings()
    assert response.ranking_rules == default_ranking_rules
    assert response.distinct_attribute is None
    assert response.displayed_attributes == ["*"]
    assert response.searchable_attributes == ["*"]
    assert response.stop_words == []
    assert response.synonyms == {}
    assert response.sortable_attributes == []
    assert response.typo_tolerance.enabled is True
    assert response.faceting.max_values_per_facet == 100
    assert response.pagination.max_total_hits == 1000
    assert response.proximity_precision is None


def test_get_ranking_rules_default(empty_index, default_ranking_rules):
    index = empty_index()
    response = index.get_ranking_rules()
    assert response == default_ranking_rules


def test_update_ranking_rules(empty_index, new_ranking_rules):
    index = empty_index()
    response = index.update_ranking_rules(new_ranking_rules)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_ranking_rules()
    assert response == new_ranking_rules


def test_reset_ranking_rules(empty_index, new_ranking_rules, default_ranking_rules):
    index = empty_index()
    response = index.update_ranking_rules(new_ranking_rules)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_ranking_rules()
    assert response == new_ranking_rules
    response = index.reset_ranking_rules()
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_ranking_rules()
    assert response == default_ranking_rules


def test_get_distinct_attribute(empty_index, default_distinct_attribute):
    index = empty_index()
    response = index.get_distinct_attribute()
    assert response == default_distinct_attribute


def test_update_distinct_attribute(empty_index, new_distinct_attribute):
    index = empty_index()
    response = index.update_distinct_attribute(new_distinct_attribute)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_distinct_attribute()
    assert response == new_distinct_attribute


def test_reset_distinct_attribute(empty_index, new_distinct_attribute, default_distinct_attribute):
    index = empty_index()
    response = index.update_distinct_attribute(new_distinct_attribute)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_distinct_attribute()
    assert response == new_distinct_attribute
    response = index.reset_distinct_attribute()
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_distinct_attribute()
    assert response == default_distinct_attribute


def test_get_searchable_attributes(empty_index, small_movies):
    index = empty_index()
    response = index.get_searchable_attributes()
    assert response == ["*"]
    response = index.add_documents(small_movies, primary_key="id")
    wait_for_task(index.http_client, response.task_uid)
    get_attributes = index.get_searchable_attributes()
    assert get_attributes == ["*"]


def test_update_searchable_attributes(empty_index, new_searchable_attributes):
    index = empty_index()
    response = index.update_searchable_attributes(new_searchable_attributes)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_searchable_attributes()
    assert response == new_searchable_attributes


def test_reset_searchable_attributes(empty_index, new_searchable_attributes):
    index = empty_index()
    response = index.update_searchable_attributes(new_searchable_attributes)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_searchable_attributes()
    assert response == new_searchable_attributes
    response = index.reset_searchable_attributes()
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_searchable_attributes()
    assert response == ["*"]


def test_get_displayed_attributes(empty_index, small_movies):
    index = empty_index()
    response = index.get_displayed_attributes()
    assert response == ["*"]
    response = index.add_documents(small_movies)
    wait_for_task(index.http_client, response.task_uid)
    get_attributes = index.get_displayed_attributes()
    assert get_attributes == ["*"]


def test_update_displayed_attributes(empty_index, displayed_attributes):
    index = empty_index()
    response = index.update_displayed_attributes(displayed_attributes)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_displayed_attributes()
    assert response == displayed_attributes


def test_reset_displayed_attributes(empty_index, displayed_attributes):
    index = empty_index()
    response = index.update_displayed_attributes(displayed_attributes)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_displayed_attributes()
    assert response == displayed_attributes
    response = index.reset_displayed_attributes()
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_displayed_attributes()
    assert response == ["*"]


def test_get_pagination(empty_index):
    index = empty_index()
    response = index.get_pagination()
    assert response.max_total_hits == 1000


def test_update_pagination(empty_index):
    pagination = Pagination(max_total_hits=17)
    index = empty_index()
    response = index.update_pagination(pagination)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_pagination()
    assert pagination.model_dump() == pagination.model_dump()


def test_reset_pagination(empty_index, default_pagination):
    index = empty_index()
    response = index.update_pagination(Pagination(max_total_hits=17))
    wait_for_task(index.http_client, response.task_uid)
    response = index.reset_pagination()
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_pagination()
    assert response.model_dump() == default_pagination.model_dump()


def test_get_separator_tokens(empty_index):
    index = empty_index()
    response = index.get_separator_tokens()
    assert response == []


def test_update_separator_tokens(empty_index):
    index = empty_index()
    expected = ["/", "|"]
    response = index.update_separator_tokens(expected)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_separator_tokens()
    assert response == expected


def test_reset_separator_tokens(empty_index):
    index = empty_index()
    expected = ["/", "|"]
    response = index.update_separator_tokens(expected)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_separator_tokens()
    assert response == expected
    response = index.reset_separator_tokens()
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_separator_tokens()
    assert response == []


def test_get_non_separator_tokens(empty_index):
    index = empty_index()
    response = index.get_non_separator_tokens()
    assert response == []


def test_update_non_separator_tokens(empty_index):
    index = empty_index()
    expected = ["#", "@"]
    response = index.update_non_separator_tokens(expected)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_non_separator_tokens()
    assert response == expected


def test_reset_non_separator_tokens(empty_index):
    index = empty_index()
    expected = ["#", "@"]
    response = index.update_non_separator_tokens(expected)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_non_separator_tokens()
    assert response == expected
    response = index.reset_non_separator_tokens()
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_non_separator_tokens()
    assert response == []


def test_get_word_dictionary(empty_index):
    index = empty_index()
    response = index.get_word_dictionary()
    assert response == []


def test_update_word_dictionary(empty_index):
    index = empty_index()
    expected = ["S.O", "S.O.S"]
    response = index.update_word_dictionary(expected)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_word_dictionary()
    assert response == expected


def test_reset_word_dictionary(empty_index):
    index = empty_index()
    expected = ["S.O", "S.O.S"]
    response = index.update_word_dictionary(expected)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_word_dictionary()
    assert response == expected
    response = index.reset_word_dictionary()
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_word_dictionary()
    assert response == []


def test_get_stop_words_default(empty_index):
    index = empty_index()
    response = index.get_stop_words()
    assert response is None


def test_update_stop_words(empty_index, new_stop_words):
    index = empty_index()
    response = index.update_stop_words(new_stop_words)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_stop_words()
    assert response == new_stop_words


def test_reset_stop_words(empty_index, new_stop_words):
    index = empty_index()
    response = index.update_stop_words(new_stop_words)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_stop_words()
    assert response == new_stop_words
    response = index.reset_stop_words()
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_stop_words()
    assert response is None


def test_get_synonyms_default(empty_index):
    index = empty_index()
    response = index.get_synonyms()
    assert response is None


def test_update_synonyms(empty_index, new_synonyms):
    index = empty_index()
    response = index.update_synonyms(new_synonyms)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_synonyms()
    assert response == new_synonyms


def test_reset_synonyms(empty_index, new_synonyms):
    index = empty_index()
    response = index.update_synonyms(new_synonyms)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_synonyms()
    assert response == new_synonyms
    response = index.reset_synonyms()
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_synonyms()
    assert response is None


def test_get_filterable_attributes(empty_index):
    index = empty_index()
    response = index.get_filterable_attributes()
    assert response is None


def test_update_filterable_attributes(empty_index, filterable_attributes):
    index = empty_index()
    response = index.update_filterable_attributes(filterable_attributes)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_filterable_attributes()
    assert sorted(response) == filterable_attributes


def test_reset_filterable_attributes(empty_index, filterable_attributes):
    index = empty_index()
    response = index.update_filterable_attributes(filterable_attributes)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_filterable_attributes()
    assert sorted(response) == filterable_attributes
    response = index.reset_filterable_attributes()
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_filterable_attributes()
    assert response is None


def test_get_sortable_attributes(empty_index):
    index = empty_index()
    response = index.get_sortable_attributes()
    assert response == []


def test_update_sortable_attributes(empty_index, sortable_attributes):
    index = empty_index()
    response = index.update_sortable_attributes(sortable_attributes)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_sortable_attributes()
    assert sorted(response) == sortable_attributes


def test_reset_sortable_attributes(empty_index, sortable_attributes):
    index = empty_index()
    response = index.update_sortable_attributes(sortable_attributes)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_sortable_attributes()
    assert response == sortable_attributes
    response = index.reset_sortable_attributes()
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_sortable_attributes()
    assert response == []


def test_get_typo_tolerance(empty_index):
    index = empty_index()
    response = index.get_typo_tolerance()
    assert response.enabled is True


def test_update_typo_tolerance(empty_index):
    typo_tolerance = TypoTolerance(
        enabled=True,
        disable_on_attributes=["title"],
        disable_on_words=["spiderman"],
        min_word_size_for_typos=MinWordSizeForTypos(one_typo=10, two_typos=20),
    )
    index = empty_index()
    response = index.update_typo_tolerance(typo_tolerance)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_typo_tolerance()
    assert response.model_dump() == typo_tolerance.model_dump()


def test_reset_typo_tolerance(empty_index):
    index = empty_index()
    response = index.update_typo_tolerance(TypoTolerance(enabled=False))
    wait_for_task(index.http_client, response.task_uid)
    response = index.reset_typo_tolerance()
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_typo_tolerance()
    assert response.enabled is True


def test_get_faceting(empty_index):
    index = empty_index()
    response = index.get_faceting()
    assert response.max_values_per_facet == 100


def test_update_faceting(empty_index):
    faceting = Faceting(max_values_per_facet=17)
    index = empty_index()
    response = index.update_faceting(faceting)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_faceting()
    expected = faceting.model_dump()
    expected["sort_facet_values_by"] = {"*": "alpha"}
    assert response.model_dump() == expected


def test_get_proximity_precision(empty_index):
    index = empty_index()
    response = index.get_proximity_precision()
    assert response is None


def test_update_proximity_precision(empty_index):
    index = empty_index()
    response = index.update_proximity_precision(ProximityPrecision.BY_ATTRIBUTE)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_proximity_precision()
    assert response == ProximityPrecision.BY_ATTRIBUTE


def test_reset_proximity_precision(empty_index):
    index = empty_index()
    response = index.update_proximity_precision(ProximityPrecision.BY_WORD)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_proximity_precision()
    assert response == ProximityPrecision.BY_WORD
    response = index.reset_proximity_precision()
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_proximity_precision()
    assert response is None


@pytest.mark.parametrize(
    "index_name, facet_order, max_values_per_facet, expected",
    (
        ("*", "alpha", 17, {"max_values_per_facet": 17, "sort_facet_values_by": {"*": "alpha"}}),
        ("*", "count", 41, {"max_values_per_facet": 41, "sort_facet_values_by": {"*": "count"}}),
        (
            "movies",
            "alpha",
            42,
            {"max_values_per_facet": 42, "sort_facet_values_by": {"*": "alpha", "movies": "alpha"}},
        ),
        (
            "movies",
            "alpha",
            73,
            {"max_values_per_facet": 73, "sort_facet_values_by": {"*": "alpha", "movies": "alpha"}},
        ),
    ),
)
def test_update_faceting_sort_facet_values(
    index_name, facet_order, max_values_per_facet, expected, empty_index
):
    faceting = Faceting(
        max_values_per_facet=max_values_per_facet,
        sort_facet_values_by={index_name: facet_order},
    )
    index = empty_index()
    response = index.update_faceting(faceting)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_faceting()
    assert response.model_dump() == expected


def test_update_faceting_sort_facet_values_invalid_sort_type():
    with pytest.raises(ValueError):
        Faceting(
            max_values_per_facet=2,
            sort_facet_values_by={"*": "bad"},
        )


def test_reset_faceting(empty_index, default_faceting):
    index = empty_index()
    response = index.update_faceting(Faceting(max_values_per_facet=17))
    wait_for_task(index.http_client, response.task_uid)
    response = index.reset_faceting()
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_faceting()
    assert response.model_dump() == default_faceting.model_dump()


def test_str(empty_index):
    index = empty_index()
    got = index.__str__()

    assert "uid" in got
    assert "primary_key" in got
    assert "created_at" in got
    assert "updated_at" in got


def test_repr(empty_index):
    index = empty_index()
    got = index.__repr__()

    assert "uid" in got
    assert "primary_key" in got
    assert "created_at" in got
    assert "updated_at" in got


@pytest.mark.usefixtures("indexes_sample")
def test_delete_if_exists(client, index_uid):
    assert client.get_index(uid=index_uid)
    deleted = client.index(index_uid).delete_if_exists()
    assert deleted is True
    with pytest.raises(MeilisearchApiError):
        client.get_index(uid=index_uid)


def test_delete_if_exists_no_delete(client):
    with pytest.raises(MeilisearchApiError):
        client.get_index(uid="none")

    deleted = client.index("none").delete_if_exists()
    assert deleted is False


@pytest.mark.usefixtures("indexes_sample")
def test_delete_if_exists_error(client, index_uid, monkeypatch):
    def mock_response(*args, **kwargs):
        raise MeilisearchApiError("test", Response(status_code=404))

    monkeypatch.setattr(HttpRequests, "_send_request", mock_response)
    with pytest.raises(MeilisearchApiError):
        client.index(index_uid).delete_if_exists()


@pytest.mark.usefixtures("indexes_sample")
def test_delete_index_if_exists(client, index_uid):
    assert client.get_index(uid=index_uid)
    deleted = client.delete_index_if_exists(index_uid)
    assert deleted is True
    with pytest.raises(MeilisearchApiError):
        client.get_index(uid=index_uid)


def test_delete_index_if_exists_no_delete(client):
    with pytest.raises(MeilisearchApiError):
        client.get_index(uid="none")

    deleted = client.delete_index_if_exists("none")
    assert deleted is False


@pytest.mark.usefixtures("indexes_sample")
def test_delete_index_if_exists_error(client, index_uid, monkeypatch):
    def mock_response(*args, **kwargs):
        raise MeilisearchApiError("test", Response(status_code=404))

    monkeypatch.setattr(HttpRequests, "_send_request", mock_response)
    with pytest.raises(MeilisearchApiError):
        client.delete_index_if_exists(index_uid)
