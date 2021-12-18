import pytest

from meilisearch_python_async.task import wait_for_task


@pytest.mark.asyncio
async def test_basic_search(index_with_documents):
    index = await index_with_documents()
    response = await index.search("How to Train Your Dragon")
    assert response.hits[0]["id"] == "166428"
    assert "_formatted" not in response.hits[0]


@pytest.mark.asyncio
async def test_basic_search_with_empty_params(index_with_documents):
    index = await index_with_documents()
    response = await index.search("How to Train Your Dragon")
    assert response.hits[0]["id"] == "166428"
    assert "_formatted" not in response.hits[0]


@pytest.mark.asyncio
async def test_search_with_empty_query(index_with_documents):
    index = await index_with_documents()
    response = await index.search("")
    assert len(response.hits) == 20
    assert response.query == ""


@pytest.mark.asyncio
async def test_custom_search(index_with_documents):
    index = await index_with_documents()
    response = await index.search("Dragon", attributes_to_highlight=["title"])
    assert response.hits[0]["id"] == "166428"
    assert "_formatted" in response.hits[0]
    assert "dragon" in response.hits[0]["_formatted"]["title"].lower()


@pytest.mark.asyncio
async def test_custom_search_with_empty_query(index_with_documents):
    index = await index_with_documents()
    response = await index.search("", attributes_to_highlight=["title"])
    assert len(response.hits) == 20
    assert response.query == ""


@pytest.mark.asyncio
async def test_custom_search_with_no_query(index_with_documents):
    index = await index_with_documents()
    response = await index.search("", limit=5)
    assert len(response.hits) == 5


@pytest.mark.asyncio
async def test_custom_search_params_with_wildcard(index_with_documents):
    index = await index_with_documents()
    response = await index.search(
        "a",
        limit=5,
        attributes_to_highlight=["*"],
        attributes_to_retrieve=["*"],
        attributes_to_crop=["*"],
    )
    assert len(response.hits) == 5
    assert "_formatted" in response.hits[0]
    assert "title" in response.hits[0]["_formatted"]


@pytest.mark.asyncio
async def test_custom_search_params_with_simple_string(index_with_documents):
    index = await index_with_documents()
    response = await index.search(
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


@pytest.mark.asyncio
async def test_custom_search_params_with_string_list(index_with_documents):
    index = await index_with_documents()
    response = await index.search(
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


@pytest.mark.asyncio
async def test_custom_search_params_with_facets_distribution(index_with_documents):
    index = await index_with_documents()
    update = await index.update_filterable_attributes(["genre"])
    await wait_for_task(index.http_client, update.uid)
    response = await index.search("world", facets_distribution=["genre"])
    assert len(response.hits) == 12
    assert response.facets_distribution is not None
    assert response.exhaustive_facets_count is not None
    assert "genre" in response.facets_distribution
    assert response.facets_distribution["genre"]["cartoon"] == 1
    assert response.facets_distribution["genre"]["action"] == 3
    assert response.facets_distribution["genre"]["fantasy"] == 1


@pytest.mark.asyncio
async def test_custom_search_params_with_facet_filters(index_with_documents):
    index = await index_with_documents()
    update = await index.update_filterable_attributes(["genre"])
    await wait_for_task(index.http_client, update.uid)
    response = await index.search("world", filter=[["genre = action"]])
    assert len(response.hits) == 3
    assert response.facets_distribution is None
    assert response.exhaustive_facets_count is None


@pytest.mark.asyncio
async def test_custom_search_params_with_multiple_facet_filters(index_with_documents):
    index = await index_with_documents()
    update = await index.update_filterable_attributes(["genre"])
    await wait_for_task(index.http_client, update.uid)
    response = await index.search(
        "world", filter=["genre = action", ["genre = action", "genre = action"]]
    )
    assert len(response.hits) == 3
    assert response.facets_distribution is None
    assert response.exhaustive_facets_count is None


@pytest.mark.asyncio
async def test_custom_search_facet_filters_with_space(test_client):
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

    index = test_client.index("books")
    update = await index.add_documents(dataset)
    await wait_for_task(index.http_client, update.uid)
    update = await index.update_filterable_attributes(["genre"])
    await wait_for_task(index.http_client, update.uid)
    response = await index.search("h", filter=["genre = 'sci fi'"])
    assert len(response.hits) == 1
    assert response.hits[0]["title"] == "The Hobbit"


@pytest.mark.asyncio
async def test_custom_search_params_with_many_params(index_with_documents):
    index = await index_with_documents()
    update = await index.update_filterable_attributes(["genre"])
    await wait_for_task(index.http_client, update.uid)
    response = await index.search(
        "world", filter=[["genre = action"]], attributes_to_retrieve=["title", "poster"]
    )
    assert len(response.hits) == 3
    assert response.facets_distribution is None
    assert response.exhaustive_facets_count is None
    assert "title" in response.hits[0]
    assert "poster" in response.hits[0]
    assert "overview" not in response.hits[0]
    assert "release_date" not in response.hits[0]
    assert response.hits[0]["title"] == "Avengers: Infinity War"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sort, titles",
    [
        (
            ["title:asc"],
            ["After", "Us"],
        ),
        (
            ["title:desc"],
            ["Us", "After"],
        ),
    ],
)
async def test_search_sort(sort, titles, index_with_documents):
    index = await index_with_documents()
    response = await index.update_sortable_attributes(["title"])
    await wait_for_task(index.http_client, response.uid)
    stats = await index.get_stats()  # get this to get the total document count

    # Using a placeholder search because ranking rules affect sort otherwaise meaning the results
    # will almost never be in alphabetical order.
    response = await index.search(sort=sort, limit=stats.number_of_documents)
    assert response.hits[0]["title"] == titles[0]
    assert response.hits[stats.number_of_documents - 1]["title"] == titles[1]
