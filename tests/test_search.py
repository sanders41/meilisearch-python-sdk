from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest
from camel_converter.pydantic_base import CamelBase

from meilisearch_python_sdk import Client
from meilisearch_python_sdk._task import wait_for_task
from meilisearch_python_sdk.errors import MeilisearchApiError, MeilisearchError
from meilisearch_python_sdk.models.search import (
    Federation,
    FederationMerged,
    Hybrid,
    MergeFacets,
    SearchParams,
)


def test_basic_search(index_with_documents):
    index = index_with_documents()
    response = index.search("How to Train Your Dragon")
    assert response.hits[0]["id"] == "166428"
    assert "_formatted" not in response.hits[0]


def test_basic_search_with_empty_params(index_with_documents):
    index = index_with_documents()
    response = index.search("How to Train Your Dragon")
    assert response.hits[0]["id"] == "166428"
    assert "_formatted" not in response.hits[0]


def test_search_with_empty_query(index_with_documents):
    index = index_with_documents()
    response = index.search("")
    assert len(response.hits) == 20
    assert response.query == ""


def test_distinct_search(index_with_documents):
    index = index_with_documents()
    task = index.update_filterable_attributes(["genre"])
    wait_for_task(index.http_client, task.task_uid)
    response = index.search("with", distinct="genre")
    genres = dict(Counter([x.get("genre") for x in response.hits]))
    assert genres == {None: 9, "action": 1}
    assert response.hits[0]["id"] == "399579"


def test_custom_search(index_with_documents):
    index = index_with_documents()
    response = index.search("Dragon", attributes_to_highlight=["title"])
    assert response.hits[0]["id"] == "166428"
    assert "_formatted" in response.hits[0]
    assert "dragon" in response.hits[0]["_formatted"]["title"].lower()


def test_custom_search_hightlight_tags_and_crop_marker(index_with_documents):
    index = index_with_documents()
    response = index.search(
        "Dragon",
        crop_length=5,
        attributes_to_highlight=["title"],
        highlight_pre_tag="<strong>",
        highlight_post_tag="</strong>",
        crop_marker="***",
    )
    assert response.hits[0]["id"] == "166428"
    assert "_formatted" in response.hits[0]
    assert "dragon" in response.hits[0]["_formatted"]["title"].lower()
    assert "<strong>" in response.hits[0]["_formatted"]["title"]
    assert "</strong>" in response.hits[0]["_formatted"]["title"]


def test_custom_search_with_empty_query(index_with_documents):
    index = index_with_documents()
    response = index.search("", attributes_to_highlight=["title"])
    assert len(response.hits) == 20
    assert response.query == ""


def test_custom_search_params_with_matching_strategy_all(index_with_documents):
    index = index_with_documents()
    response = index.search("man loves", limit=5, matching_strategy="all")

    assert len(response.hits) == 1


def test_custom_search_params_with_matching_strategy_last(index_with_documents):
    index = index_with_documents()
    response = index.search("man loves", limit=5, matching_strategy="last")

    assert len(response.hits) > 1


def test_custom_search_with_no_query(index_with_documents):
    index = index_with_documents()
    response = index.search("", limit=5)
    assert len(response.hits) == 5


def test_custom_search_params_with_wildcard(index_with_documents):
    index = index_with_documents()
    response = index.search(
        "a",
        limit=5,
        attributes_to_highlight=["*"],
        attributes_to_retrieve=["*"],
        attributes_to_crop=["*"],
    )
    assert len(response.hits) == 5
    assert "_formatted" in response.hits[0]
    assert "title" in response.hits[0]["_formatted"]


def test_custom_search_params_with_simple_string(index_with_documents):
    index = index_with_documents()
    response = index.search(
        "a",
        limit=5,
        attributes_to_highlight=["title"],
        attributes_to_retrieve=["title"],
        attributes_to_crop=["title"],
    )
    assert len(response.hits) == 5
    assert "_formatted" in response.hits[0]
    assert "title" in response.hits[0]["_formatted"]
    assert "release_date" not in response.hits[0]["_formatted"]


def test_custom_search_params_with_string_list(index_with_documents):
    index = index_with_documents()
    response = index.search(
        "Shazam!",
        limit=5,
        attributes_to_retrieve=["title", "overview"],
        attributes_to_highlight=["title"],
    )
    assert len(response.hits) == 1
    assert "title" in response.hits[0]
    assert "overview" in response.hits[0]
    assert "release_date" not in response.hits[0]
    assert "<em>" in response.hits[0]["_formatted"]["title"]
    assert "<em>" not in response.hits[0]["_formatted"]["overview"]


def test_custom_search_params_with_facets(index_with_documents):
    index = index_with_documents()
    update = index.update_filterable_attributes(["genre"])
    wait_for_task(index.http_client, update.task_uid)
    response = index.search("world", facets=["genre"])
    assert len(response.hits) == 12
    assert response.facet_distribution is not None
    assert "genre" in response.facet_distribution
    assert response.facet_distribution["genre"]["cartoon"] == 1
    assert response.facet_distribution["genre"]["action"] == 3
    assert response.facet_distribution["genre"]["fantasy"] == 1


def test_custom_search_params_with_facet_filters(index_with_documents):
    index = index_with_documents()
    update = index.update_filterable_attributes(["genre"])
    wait_for_task(index.http_client, update.task_uid)
    response = index.search("world", filter=[["genre = action"]])
    assert len(response.hits) == 3
    assert response.facet_distribution is None


def test_custom_search_params_with_multiple_facet_filters(index_with_documents):
    index = index_with_documents()
    update = index.update_filterable_attributes(["genre"])
    wait_for_task(index.http_client, update.task_uid)
    response = index.search(
        "world", filter=["genre = action", ["genre = action", "genre = action"]]
    )
    assert len(response.hits) == 3
    assert response.facet_distribution is None


def test_custom_search_facet_filters_with_space(client):
    dataset = [
        {
            "id": 123,
            "title": "Pride and Prejudice",
            "comment": "A great book",
            "genre": "romance",
        },
        {
            "id": 456,
            "title": "Le Petit Prince",
            "comment": "A french book about a prince that walks on little cute planets",
            "genre": "adventure",
        },
        {
            "id": 2,
            "title": "Le Rouge et le Noir",
            "comment": "Another french book",
            "genre": "romance",
        },
        {
            "id": 1,
            "title": "Alice In Wonderland",
            "comment": "A weird book",
            "genre": "adventure",
        },
        {
            "id": 1344,
            "title": "The Hobbit",
            "comment": "An awesome book",
            "genre": "sci fi",
        },
        {
            "id": 4,
            "title": "Harry Potter and the Half-Blood Prince",
            "comment": "The best book",
            "genre": "fantasy",
        },
        {"id": 42, "title": "The Hitchhiker's Guide to the Galaxy", "genre": "fantasy"},
    ]

    index = client.index("books")
    update = index.add_documents(dataset)
    wait_for_task(index.http_client, update.task_uid)
    update = index.update_filterable_attributes(["genre"])
    wait_for_task(index.http_client, update.task_uid)
    response = index.search("h", filter=["genre = 'sci fi'"])
    assert len(response.hits) == 1
    assert response.hits[0]["title"] == "The Hobbit"


def test_custom_search_params_with_pagination_parameters(index_with_documents):
    index = index_with_documents()
    response = index.search("", hits_per_page=1, page=1)

    assert len(response.hits) == 1
    assert response.hits_per_page == 1
    assert response.page == 1
    assert response.total_pages is not None
    assert response.total_hits is not None


def test_custom_search_params_with_pagination_parameters_at_zero(index_with_documents):
    index = index_with_documents()
    response = index.search("", hits_per_page=0, page=0)

    assert len(response.hits) == 0
    assert response.hits_per_page == 0
    assert response.page == 0
    assert response.total_pages is not None
    assert response.total_hits is not None
    assert response.estimated_total_hits is None


def test_custom_search_params_with_many_params(index_with_documents):
    index = index_with_documents()
    update = index.update_filterable_attributes(["genre"])
    wait_for_task(index.http_client, update.task_uid)
    response = index.search(
        "world", filter=[["genre = action"]], attributes_to_retrieve=["title", "poster"]
    )
    assert len(response.hits) == 3
    assert response.facet_distribution is None
    assert "title" in response.hits[0]
    assert "poster" in response.hits[0]
    assert "overview" not in response.hits[0]
    assert "release_date" not in response.hits[0]
    assert response.hits[0]["title"] == "Avengers: Infinity War"


@pytest.mark.parametrize(
    "sort, titles",
    (
        (
            ["title:asc"],
            ["After", "Us"],
        ),
        (
            ["title:desc"],
            ["Us", "After"],
        ),
    ),
)
def test_search_sort(sort, titles, index_with_documents):
    index = index_with_documents()
    response = index.update_sortable_attributes(["title"])
    wait_for_task(index.http_client, response.task_uid)
    stats = index.get_stats()  # get this to get the total document count

    # Using a placeholder search because ranking rules affect sort otherwaise meaning the results
    # will almost never be in alphabetical order.
    response = index.search(sort=sort, limit=stats.number_of_documents)
    assert response.hits[0]["title"] == titles[0]
    assert response.hits[stats.number_of_documents - 1]["title"] == titles[1]


@pytest.mark.no_parallel
def test_search_with_tenant_token(
    client, index_with_documents, base_url, default_search_key, ssl_verify
):
    token = client.generate_tenant_token(search_rules=["*"], api_key=default_search_key)
    index_docs = index_with_documents()

    client = Client(base_url, token, verify=ssl_verify)
    index = client.index(index_docs.uid)
    response = index.search("How to Train Your Dragon")

    assert response.hits[0]["id"] == "166428"


@pytest.mark.no_parallel
def test_search_with_tenant_token_and_expire_date(
    client, index_with_documents, base_url, default_search_key, ssl_verify
):
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=1)
    token = client.generate_tenant_token(
        search_rules=["*"], api_key=default_search_key, expires_at=expires_at
    )
    index_docs = index_with_documents()

    client = Client(base_url, token, verify=ssl_verify)
    index = client.index(index_docs.uid)
    response = index.search("How to Train Your Dragon")

    assert response.hits[0]["id"] == "166428"


def test_multi_search(client, index_with_documents, empty_index):
    index1 = index_with_documents()
    index2 = empty_index()
    response = client.multi_search(
        [
            SearchParams(index_uid=index1.uid, query="How to Train Your Dragon"),
            SearchParams(index_uid=index2.uid, query=""),
        ]
    )

    assert isinstance(response[0].hits[0], dict)
    assert response[0].index_uid == index1.uid
    assert response[0].hits[0]["id"] == "166428"
    assert "_formatted" not in response[0].hits[0]
    assert response[1].index_uid == index2.uid


def test_multi_search_generic(client, index_with_documents):
    class Movie(CamelBase):
        id: int
        title: str
        poster: str
        overview: str
        release_date: datetime
        genre: str | None = None

    index1 = index_with_documents()
    index2 = index_with_documents()
    response = client.multi_search(
        [
            SearchParams(index_uid=index1.uid, query="How to Train Your Dragon"),
            SearchParams(index_uid=index2.uid, query=""),
        ],
        hits_type=Movie,
    )

    assert isinstance(response[0].hits[0], Movie)
    assert isinstance(response[1].hits[0], Movie)
    assert response[0].index_uid == index1.uid
    assert response[0].hits[0].id == 166428
    assert response[1].index_uid == index2.uid


def test_multi_search_one_index(client, index_with_documents):
    index = index_with_documents()
    response = client.multi_search(
        [SearchParams(index_uid=index.uid, query="How to Train Your Dragon")]
    )
    assert response[0].hits[0]["id"] == "166428"
    assert "_formatted" not in response[0].hits[0]


def test_multi_search_no_index(client):
    with pytest.raises(MeilisearchApiError):
        client.multi_search(
            [SearchParams(index_uid="bad", query="How to Train Your Dragon")],
        )


def test_multi_search_federated(client, index_with_documents, empty_index):
    index1 = index_with_documents()
    index2 = empty_index()
    response = client.multi_search(
        [
            SearchParams(index_uid=index1.uid, query="How to Train Your Dragon"),
            SearchParams(index_uid=index2.uid, query=""),
        ],
        federation=Federation(),
    )

    assert response.hits[0]["id"] == "166428"
    assert "_formatted" not in response.hits[0]
    assert "_federation" in response.hits[0]


def test_multi_search_federated_merge_facets(
    client,
    index_with_documents,
    empty_index,
):
    index1 = index_with_documents()
    task = index1.update_filterable_attributes(["title"])
    client.wait_for_task(task.task_uid)
    index2 = empty_index()
    federation = FederationMerged(merge_facets=MergeFacets(max_values_per_facet=10))
    federation.facets_by_index = {index1.uid: ["title"]}
    response = client.multi_search(
        [
            SearchParams(index_uid=index1.uid, query="How to Train Your Dragon"),
            SearchParams(index_uid=index2.uid, query=""),
        ],
        federation=federation,
    )

    assert response.hits[0]["id"] == "166428"
    assert "_formatted" not in response.hits[0]
    assert "_federation" in response.hits[0]
    assert response.facets_by_index is None
    assert response.facet_distribution is not None


def test_multi_search_locales(client, index_with_documents, empty_index):
    index1 = index_with_documents()
    index2 = empty_index()
    response = client.multi_search(
        [
            SearchParams(
                index_uid=index1.uid, query="How to Train Your Dragon", locales=["eng", "spa"]
            ),
            SearchParams(index_uid=index2.uid, query="", locales=["fra"]),
        ]
    )

    assert response[0].index_uid == index1.uid
    assert response[0].hits[0]["id"] == "166428"
    assert "_formatted" not in response[0].hits[0]
    assert response[1].index_uid == index2.uid


def test_attributes_to_search_on_search(index_with_documents):
    index = index_with_documents()
    response = index.search(
        "How to Train Your Dragon", attributes_to_search_on=["title", "overview"]
    )
    assert response.hits[0]["id"] == "166428"


def test_attributes_to_search_on_search_no_match(index_with_documents):
    index = index_with_documents()
    response = index.search("How to Train Your Dragon", attributes_to_search_on=["id"])
    assert response.hits == []


def test_show_ranking_score_serach(index_with_documents):
    index = index_with_documents()
    response = index.search("How to Train Your Dragon", show_ranking_score=True)
    assert response.hits[0]["id"] == "166428"
    assert "_rankingScore" in response.hits[0]


def test_show_ranking_details_serach(index_with_documents):
    index = index_with_documents()
    response = index.search("How to Train Your Dragon", show_ranking_score_details=True)
    assert response.hits[0]["id"] == "166428"
    assert "_rankingScoreDetails" in response.hits[0]


def test_vector_search(index_with_documents_and_vectors):
    index = index_with_documents_and_vectors()
    response = index.search(
        "",
        vector=[0.1, 0.2],
        hybrid=Hybrid(semantic_ratio=1.0, embedder="default"),
    )
    assert len(response.hits) >= 1


def test_vector_search_retrieve_vectors(index_with_documents_and_vectors):
    index = index_with_documents_and_vectors()
    response = index.search(
        "",
        vector=[0.1, 0.2],
        hybrid=Hybrid(semantic_ratio=1.0, embedder="default"),
        retrieve_vectors=True,
    )
    assert len(response.hits) >= 1
    assert response.hits[0].get("_vectors") is not None


def test_vector_search_retrieve_vectors_false(index_with_documents_and_vectors):
    index = index_with_documents_and_vectors()
    response = index.search(
        "",
        vector=[0.1, 0.2],
        hybrid=Hybrid(semantic_ratio=1.0, embedder="default"),
        retrieve_vectors=False,
    )
    assert len(response.hits) >= 1
    assert response.hits[0].get("_vectors") is None


def test_basic_facet_search(index_with_documents):
    index = index_with_documents()
    update = index.update_filterable_attributes(["genre"])
    wait_for_task(index.http_client, update.task_uid)
    response = index.facet_search(
        "How to Train Your Dragon", facet_name="genre", facet_query="cartoon"
    )
    assert response.facet_hits[0].value == "cartoon"
    assert response.facet_hits[0].count == 1


def test_basic_facet_search_not_found(index_with_documents):
    index = index_with_documents()
    update = index.update_filterable_attributes(["genre"])
    wait_for_task(index.http_client, update.task_uid)
    response = index.facet_search(
        "How to Train Your Dragon", facet_name="genre", facet_query="horror"
    )
    assert response.facet_hits == []


def test_custom_facet_search(index_with_documents):
    index = index_with_documents()
    update = index.update_filterable_attributes(["genre"])
    wait_for_task(index.http_client, update.task_uid)
    response = index.facet_search(
        "Dragon",
        facet_name="genre",
        facet_query="cartoon",
        attributes_to_highlight=["title"],
    )
    assert response.facet_hits[0].value == "cartoon"
    assert response.facet_hits[0].count == 1


def test_facet_search_locales(index_with_documents):
    index = index_with_documents()
    update = index.update_filterable_attributes(["genre"])
    wait_for_task(index.http_client, update.task_uid)
    response = index.facet_search(
        "How to Train Your Dragon",
        facet_name="genre",
        facet_query="cartoon",
        locales=["eng", "spa"],
    )
    assert response.facet_hits[0].value == "cartoon"
    assert response.facet_hits[0].count == 1


def test_facet_search_exhaustive_facet_count(index_with_documents):
    index = index_with_documents()
    update = index.update_filterable_attributes(["genre"])
    wait_for_task(index.http_client, update.task_uid)
    response = index.facet_search(
        "How to Train Your Dragon",
        facet_name="genre",
        facet_query="cartoon",
        exhaustive_facet_count=True,
    )

    assert response.facet_hits[0].value == "cartoon"


@pytest.mark.parametrize("ranking_score_threshold", (-0.1, 1.1))
def test_search_invalid_ranking_score_threshold(
    ranking_score_threshold, index_with_documents_and_vectors
):
    index = index_with_documents_and_vectors()
    with pytest.raises(MeilisearchError) as e:
        index.search("", ranking_score_threshold=ranking_score_threshold)
        assert "ranking_score_threshold must be between 0.0 and 1.0" in str(e.value)


def test_search_ranking_score_threshold(index_with_documents_and_vectors):
    index = index_with_documents_and_vectors()
    result = index.search("", ranking_score_threshold=0.5)
    assert len(result.hits) > 0


@pytest.mark.parametrize("ranking_score_threshold", (-0.1, 1.1))
def test_multi_search_invalid_ranking_score_threshold(
    ranking_score_threshold, client, index_with_documents
):
    index1 = index_with_documents()
    with pytest.raises(MeilisearchError) as e:
        client.multi_search(
            [
                SearchParams(
                    index_uid=index1.uid, query="", ranking_score_threshold=ranking_score_threshold
                ),
            ]
        )
        assert "ranking_score_threshold must be between 0.0 and 1.0" in str(e.value)


def test_multi_search_ranking_score_threshold(client, index_with_documents):
    index1 = index_with_documents()
    result = client.multi_search(
        [
            SearchParams(index_uid=index1.uid, query="", ranking_score_threshold=0.5),
        ]
    )
    assert len(result[0].hits) > 0


def test_facet_search_ranking_score_threshold(index_with_documents_and_vectors):
    index = index_with_documents_and_vectors()
    update = index.update_filterable_attributes(["genre"])
    wait_for_task(index.http_client, update.task_uid)
    response = index.facet_search(
        "How to Train Your Dragon",
        facet_name="genre",
        facet_query="cartoon",
        ranking_score_threshold=0.5,
    )
    assert len(response.facet_hits) > 0


@pytest.mark.parametrize("ranking_score_threshold", (-0.1, 1.1))
def test_facet_search_invalid_ranking_score_threshold(
    ranking_score_threshold, index_with_documents_and_vectors
):
    index = index_with_documents_and_vectors()
    update = index.update_filterable_attributes(["genre"])
    wait_for_task(index.http_client, update.task_uid)
    with pytest.raises(MeilisearchError) as e:
        index.facet_search(
            "How to Train Your Dragon",
            facet_name="genre",
            facet_query="cartoon",
            ranking_score_threshold=ranking_score_threshold,
        )
        assert "ranking_score_threshold must be between 0.0 and 1.0" in str(e.value)


@pytest.mark.parametrize("limit, offset", ((1, 1), (None, None)))
def test_similar_search(limit, offset, index_with_documents_and_vectors):
    index = index_with_documents_and_vectors()
    response = index.search_similar_documents("287947", limit=limit, offset=offset)
    assert len(response.hits) >= 1


def test_search_locales(index_with_documents):
    index = index_with_documents()
    response = index.search("How to Train Your Dragon", locales=["eng"])
    assert response.hits[0]["id"] == "166428"
    assert "_formatted" not in response.hits[0]


def test_search_result_hits_generic_default(index_with_documents):
    index = index_with_documents()
    response = index.search("How to Train Your Dragon")
    assert isinstance(response.hits[0], dict)
    assert response.hits[0]["id"] == "166428"


def test_search_result_hits_generic(index_with_documents):
    class Movie(CamelBase):
        id: int
        title: str
        poster: str
        overview: str
        release_date: datetime
        genre: str | None = None

    index = index_with_documents()
    index.hits_type = Movie
    response = index.search("How to Train Your Dragon")
    assert isinstance(response.hits[0], Movie)
    assert response.hits[0].id == 166428


def test_search_show_matches_position(index_with_documents):
    index = index_with_documents()
    response = index.search("with", show_matches_position=True)
    assert "_matchesPosition" in response.hits[0]
