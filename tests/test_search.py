from datetime import datetime, timedelta, timezone

import pytest

from meilisearch_python_sdk import Client
from meilisearch_python_sdk._task import wait_for_task
from meilisearch_python_sdk.errors import MeilisearchApiError
from meilisearch_python_sdk.models.search import SearchParams


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
        "a",
        limit=5,
        attributes_to_retrieve=["title", "overview"],
        attributes_to_highlight=["title"],
    )
    assert len(response.hits) == 5
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


def test_search_with_tenant_token(
    client, index_with_documents, base_url, default_search_key
):
    token = client.generate_tenant_token(search_rules=["*"], api_key=default_search_key)
    index_docs = index_with_documents()

    client = Client(base_url, token)
    index = client.index(index_docs.uid)
    response = index.search("How to Train Your Dragon")

    assert response.hits[0]["id"] == "166428"


def test_search_with_tenant_token_and_expire_date(
    client, index_with_documents, base_url, default_search_key
):
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=1)
    token = client.generate_tenant_token(
        search_rules=["*"], api_key=default_search_key, expires_at=expires_at
    )
    index_docs = index_with_documents()

    client = Client(base_url, token)
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

    assert response[0].index_uid == index1.uid
    assert response[0].hits[0]["id"] == "166428"
    assert "_formatted" not in response[0].hits[0]
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


@pytest.mark.usefixtures("enable_score_details")
def test_show_ranking_details_serach(index_with_documents):
    index = index_with_documents()
    response = index.search("How to Train Your Dragon", show_ranking_score_details=True)
    assert response.hits[0]["id"] == "166428"
    assert "_rankingScoreDetails" in response.hits[0]


@pytest.mark.usefixtures("enable_vector_search")
def test_vector_search(index_with_documents_and_vectors):
    index = index_with_documents_and_vectors()
    response = index.search("How to Train Your Dragon", vector=[0.1, 0.2])
    assert response.hits[0]["id"] == "287947"
    assert response.vector == [0.1, 0.2]


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
