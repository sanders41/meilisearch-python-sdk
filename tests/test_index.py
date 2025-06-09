import pytest
from httpx import Response

from meilisearch_python_sdk._http_requests import HttpRequests
from meilisearch_python_sdk._task import wait_for_task
from meilisearch_python_sdk.errors import MeilisearchApiError
from meilisearch_python_sdk.models.settings import (
    Embedders,
    Faceting,
    Filter,
    FilterableAttributeFeatures,
    FilterableAttributes,
    LocalizedAttributes,
    MinWordSizeForTypos,
    OpenAiEmbedder,
    Pagination,
    ProximityPrecision,
    RestEmbedder,
    TypoTolerance,
    UserProvidedEmbedder,
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
def default_pagination():
    return Pagination(max_total_hits=1000)


@pytest.fixture
def sortable_attributes():
    return ["genre", "title"]


def test_delete_index(client, indexes_sample):
    _, index_uid, index_uid2 = indexes_sample
    response = client.index(uid=index_uid).delete()
    wait_for_task(client, response.task_uid)

    with pytest.raises(MeilisearchApiError):
        client.get_index(uid=index_uid)

    response = client.index(uid=index_uid2).delete()
    wait_for_task(client, response.task_uid)

    with pytest.raises(MeilisearchApiError):
        client.get_index(uid=index_uid2)


def test_update_index(client, indexes_sample):
    _, index_uid, _ = indexes_sample
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
    assert response.proximity_precision is ProximityPrecision.BY_WORD
    assert response.separator_tokens == []
    assert response.non_separator_tokens == []
    assert response.search_cutoff_ms is None
    assert response.dictionary == []
    assert response.embedders == {}
    assert response.facet_search is True
    assert response.prefix_search == "indexingTime"


@pytest.mark.parametrize("compress", (True, False))
def test_update_settings(compress, empty_index, new_settings):
    index = empty_index()
    response = index.update_settings(new_settings, compress=compress)
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
    assert response.search_cutoff_ms == new_settings.search_cutoff_ms
    assert response.dictionary == new_settings.dictionary
    assert response.localized_attributes is None
    assert response.facet_search is False
    assert response.prefix_search == "disabled"


@pytest.mark.parametrize("compress", (True, False))
def test_update_settings_localized(compress, empty_index, new_settings_localized):
    index = empty_index()
    response = index.update_settings(new_settings_localized, compress=compress)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_settings()
    assert response.ranking_rules == new_settings_localized.ranking_rules
    assert response.distinct_attribute is None
    assert response.searchable_attributes == new_settings_localized.searchable_attributes
    assert response.displayed_attributes == ["*"]
    assert response.stop_words == []
    assert response.synonyms == {}
    assert response.sortable_attributes == new_settings_localized.sortable_attributes
    assert response.typo_tolerance.enabled is False
    assert (
        response.faceting.max_values_per_facet
        == new_settings_localized.faceting.max_values_per_facet
        == 123
    )
    assert response.pagination == new_settings_localized.pagination
    assert response.proximity_precision == new_settings_localized.proximity_precision
    assert response.separator_tokens == new_settings_localized.separator_tokens
    assert response.non_separator_tokens == new_settings_localized.non_separator_tokens
    assert response.search_cutoff_ms == new_settings_localized.search_cutoff_ms
    assert response.dictionary == new_settings_localized.dictionary
    assert response.localized_attributes == new_settings_localized.localized_attributes


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
    assert response.proximity_precision is ProximityPrecision.BY_WORD
    assert response.embedders == {}


def test_get_ranking_rules_default(empty_index, default_ranking_rules):
    index = empty_index()
    response = index.get_ranking_rules()
    assert response == default_ranking_rules


@pytest.mark.parametrize("compress", (True, False))
def test_update_ranking_rules(compress, empty_index, new_ranking_rules):
    index = empty_index()
    response = index.update_ranking_rules(new_ranking_rules, compress=compress)
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


@pytest.mark.parametrize("compress", (True, False))
def test_update_distinct_attribute(compress, empty_index, new_distinct_attribute):
    index = empty_index()
    response = index.update_distinct_attribute(new_distinct_attribute, compress=compress)
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


@pytest.mark.parametrize("compress", (True, False))
def test_update_searchable_attributes(compress, empty_index, new_searchable_attributes):
    index = empty_index()
    response = index.update_searchable_attributes(new_searchable_attributes, compress=compress)
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


@pytest.mark.parametrize("compress", (True, False))
def test_update_displayed_attributes(compress, empty_index, displayed_attributes):
    index = empty_index()
    response = index.update_displayed_attributes(displayed_attributes, compress=compress)
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


@pytest.mark.parametrize("compress", (True, False))
def test_update_pagination(compress, empty_index):
    pagination = Pagination(max_total_hits=17)
    index = empty_index()
    response = index.update_pagination(pagination, compress=compress)
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


@pytest.mark.parametrize("compress", (True, False))
def test_update_separator_tokens(compress, empty_index):
    index = empty_index()
    expected = ["/", "|"]
    response = index.update_separator_tokens(expected, compress=compress)
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


@pytest.mark.parametrize("compress", (True, False))
def test_update_non_separator_tokens(compress, empty_index):
    index = empty_index()
    expected = ["#", "@"]
    response = index.update_non_separator_tokens(expected, compress=compress)
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


def test_get_search_cutoff_ms(empty_index):
    index = empty_index()
    response = index.get_search_cutoff_ms()
    assert response is None


@pytest.mark.parametrize("compress", (True, False))
def test_update_search_cutoff_ms(compress, empty_index):
    index = empty_index()
    expected = 100
    response = index.update_search_cutoff_ms(expected, compress=compress)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_search_cutoff_ms()
    assert response == expected


def test_reset_search_cutoff_ms(empty_index):
    index = empty_index()
    expected = 100
    response = index.update_search_cutoff_ms(expected)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_search_cutoff_ms()
    assert response == expected
    response = index.reset_search_cutoff_ms()
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_search_cutoff_ms()
    assert response is None


def test_get_word_dictionary(empty_index):
    index = empty_index()
    response = index.get_word_dictionary()
    assert response == []


@pytest.mark.parametrize("compress", (True, False))
def test_update_word_dictionary(compress, empty_index):
    index = empty_index()
    expected = ["S.O", "S.O.S"]
    response = index.update_word_dictionary(expected, compress=compress)
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


@pytest.mark.parametrize("compress", (True, False))
def test_update_stop_words(compress, empty_index, new_stop_words):
    index = empty_index()
    response = index.update_stop_words(new_stop_words, compress=compress)
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


@pytest.mark.parametrize("compress", (True, False))
def test_update_synonyms(compress, empty_index, new_synonyms):
    index = empty_index()
    response = index.update_synonyms(new_synonyms, compress=compress)
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


@pytest.mark.parametrize("compress", (True, False))
@pytest.mark.parametrize(
    "filterable_attributes",
    (
        ["release_date", "title"],
        [
            FilterableAttributes(
                attribute_patterns=["release_date", "title"],
                features=FilterableAttributeFeatures(
                    facet_search=True, filter=Filter(equality=True, comparison=False)
                ),
            ),
        ],
    ),
)
def test_update_filterable_attributes(compress, empty_index, filterable_attributes):
    index = empty_index()
    response = index.update_filterable_attributes(filterable_attributes, compress=compress)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_filterable_attributes()
    assert sorted(response) == filterable_attributes


@pytest.mark.parametrize(
    "filterable_attributes",
    (
        ["release_date", "title"],
        [
            FilterableAttributes(
                attribute_patterns=["release_date", "title"],
                features=FilterableAttributeFeatures(
                    facet_search=True, filter=Filter(equality=True, comparison=False)
                ),
            ),
        ],
    ),
)
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


@pytest.mark.parametrize("compress", (True, False))
def test_update_sortable_attributes(compress, empty_index, sortable_attributes):
    index = empty_index()
    response = index.update_sortable_attributes(sortable_attributes, compress=compress)
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


@pytest.mark.parametrize("compress", (True, False))
def test_update_typo_tolerance(compress, empty_index):
    typo_tolerance = TypoTolerance(
        enabled=True,
        disable_on_attributes=["title"],
        disable_on_words=["spiderman"],
        disable_on_numbers=True,
        min_word_size_for_typos=MinWordSizeForTypos(one_typo=10, two_typos=20),
    )
    index = empty_index()
    response = index.update_typo_tolerance(typo_tolerance, compress=compress)
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


@pytest.mark.parametrize("compress", (True, False))
def test_update_faceting(compress, empty_index):
    faceting = Faceting(max_values_per_facet=17)
    index = empty_index()
    response = index.update_faceting(faceting, compress=compress)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_faceting()
    expected = faceting.model_dump()
    expected["sort_facet_values_by"] = {"*": "alpha"}
    assert response.model_dump() == expected


def test_get_proximity_precision(empty_index):
    index = empty_index()
    response = index.get_proximity_precision()
    assert response is ProximityPrecision.BY_WORD


@pytest.mark.parametrize("compress", (True, False))
def test_update_proximity_precision(compress, empty_index):
    index = empty_index()
    response = index.update_proximity_precision(ProximityPrecision.BY_ATTRIBUTE, compress=compress)
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
    assert response is ProximityPrecision.BY_WORD


def test_get_embedders(empty_index):
    index = empty_index()
    response = index.get_embedders()
    assert response is None


# NOTE: Compressing embedder settings is broken in Meilisearch 1.8.0-rc.1+ so skip testing compressing
# @pytest.mark.parametrize("compress", (True, False))
def test_update_embedders(empty_index):
    embedders = Embedders(
        embedders={
            "default": UserProvidedEmbedder(dimensions=512),
            "test2": OpenAiEmbedder(),
            "test4": RestEmbedder(
                url="https://myurl.com",
                dimensions=512,
                headers={"header1": "header value 1"},
                request={"request": {"model": "minillm", "prompt": "{{text}}"}},
                response={"response": {"embedding": "{{embedding}}"}},
            ),
        }
    )
    index = empty_index()
    response = index.update_embedders(embedders)
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_embedders()
    assert response.embedders["default"].source == "userProvided"
    assert response.embedders["test2"].source == "openAi"
    assert response.embedders["test4"].source == "rest"


def test_reset_embedders(empty_index):
    embedders = Embedders(
        embedders={
            "default": UserProvidedEmbedder(dimensions=512),
            "test2": OpenAiEmbedder(),
            "test4": RestEmbedder(
                url="https://myurl.com",
                dimensions=512,
                headers={"header1": "header value 1"},
                request={"request": {"model": "minillm", "prompt": "{{text}}"}},
                response={"response": {"embedding": "{{embedding}}"}},
            ),
        }
    )
    index = empty_index()
    response = index.update_embedders(embedders)
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"
    response = index.get_embedders()
    assert response.embedders["default"].source == "userProvided"
    assert response.embedders["test2"].source == "openAi"
    assert response.embedders["test4"].source == "rest"
    response = index.reset_embedders()
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_embedders()
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
@pytest.mark.parametrize("compress", (True, False))
def test_update_faceting_sort_facet_values(
    index_name, facet_order, max_values_per_facet, expected, compress, empty_index
):
    faceting = Faceting(
        max_values_per_facet=max_values_per_facet,
        sort_facet_values_by={index_name: facet_order},
    )
    index = empty_index()
    response = index.update_faceting(faceting, compress=compress)
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


def test_delete_if_exists(client, indexes_sample):
    _, index_uid, _ = indexes_sample
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


def test_delete_if_exists_error(client, indexes_sample, monkeypatch):
    def mock_response(*args, **kwargs):
        raise MeilisearchApiError("test", Response(status_code=404))

    _, index_uid, _ = indexes_sample
    monkeypatch.setattr(HttpRequests, "_send_request", mock_response)
    with pytest.raises(MeilisearchApiError):
        client.index(index_uid).delete_if_exists()


def test_delete_index_if_exists(client, indexes_sample):
    _, index_uid, _ = indexes_sample
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


def test_delete_index_if_exists_error(client, indexes_sample, monkeypatch):
    def mock_response(*args, **kwargs):
        raise MeilisearchApiError("test", Response(status_code=404))

    _, index_uid, _ = indexes_sample
    monkeypatch.setattr(HttpRequests, "_send_request", mock_response)
    with pytest.raises(MeilisearchApiError):
        client.delete_index_if_exists(index_uid)


def test_get_localized_attributes(empty_index):
    index = empty_index()
    response = index.get_localized_attributes()
    assert response is None


@pytest.mark.parametrize("compress", (True, False))
def test_update_localized_attributes(compress, empty_index):
    index = empty_index()
    response = index.update_localized_attributes(
        [
            LocalizedAttributes(locales=["eng", "spa"], attribute_patterns=["*"]),
            LocalizedAttributes(locales=["ita"], attribute_patterns=["*_it"]),
        ],
        compress=compress,
    )
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_localized_attributes()
    assert response == [
        LocalizedAttributes(locales=["eng", "spa"], attribute_patterns=["*"]),
        LocalizedAttributes(locales=["ita"], attribute_patterns=["*_it"]),
    ]


def test_reset_localized_attributes(empty_index):
    index = empty_index()
    response = index.update_localized_attributes(
        [
            LocalizedAttributes(locales=["eng", "spa"], attribute_patterns=["*"]),
            LocalizedAttributes(locales=["ita"], attribute_patterns=["*_it"]),
        ]
    )
    update = wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"

    response = index.get_localized_attributes()
    assert response == [
        LocalizedAttributes(locales=["eng", "spa"], attribute_patterns=["*"]),
        LocalizedAttributes(locales=["ita"], attribute_patterns=["*_it"]),
    ]

    response = index.reset_localized_attributes()
    wait_for_task(index.http_client, response.task_uid)
    response = index.get_localized_attributes()
    assert response is None


def test_get_facet_search_opt_out(empty_index):
    index = empty_index()
    response = index.get_facet_search()
    assert response is True


def test_update_facet_search_opt_out(empty_index):
    index = empty_index()
    task = index.update_facet_search(False)
    wait_for_task(index.http_client, task.task_uid)
    result = index.get_settings()

    assert result.facet_search is False


def test_reset_facet_search_opt_out(empty_index):
    index = empty_index()
    task = index.update_facet_search(False)
    wait_for_task(index.http_client, task.task_uid)
    result = index.get_settings()

    assert result.facet_search is False

    task = index.reset_facet_search()
    wait_for_task(index.http_client, task.task_uid)
    result = index.get_settings()

    assert result.facet_search is True


def test_get_prefix_search_opt_out(empty_index):
    index = empty_index()
    response = index.get_prefix_search()
    assert response == "indexingTime"


def test_update_prefix_search_opt_out(empty_index):
    index = empty_index()
    task = index.update_prefix_search("disabled")
    wait_for_task(index.http_client, task.task_uid)
    result = index.get_settings()

    assert result.prefix_search == "disabled"


def test_reset_prefix_search_opt_out(empty_index):
    index = empty_index()
    task = index.update_prefix_search("disabled")
    wait_for_task(index.http_client, task.task_uid)
    result = index.get_settings()

    assert result.prefix_search == "disabled"

    task = index.reset_prefix_search()
    wait_for_task(index.http_client, task.task_uid)
    result = index.get_settings()

    assert result.prefix_search == "indexingTime"
