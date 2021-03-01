import pytest


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
    assert "title" in response.hits[0]["_formatted"]
    assert "overview" not in response.hits[0]["_formatted"]


@pytest.mark.asyncio
async def test_custom_search_params_with_facets_distribution(index_with_documents):
    index = await index_with_documents()
    update = await index.update_attributes_for_faceting(["genre"])
    await index.wait_for_pending_update(update.update_id)
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
    update = await index.update_attributes_for_faceting(["genre"])
    await index.wait_for_pending_update(update.update_id)
    response = await index.search("world", facet_filters=[["genre:action"]])
    assert len(response.hits) == 3
    assert response.facets_distribution is None
    assert response.exhaustive_facets_count is None


@pytest.mark.asyncio
async def test_custom_search_params_with_multiple_facet_filters(index_with_documents):
    index = await index_with_documents()
    update = await index.update_attributes_for_faceting(["genre"])
    await index.wait_for_pending_update(update.update_id)
    response = await index.search(
        "world", facet_filters=["genre:action", ["genre:action", "genre:action"]]
    )
    assert len(response.hits) == 3
    assert response.facets_distribution is None
    assert response.exhaustive_facets_count is None


@pytest.mark.asyncio
async def test_custom_search_params_with_many_params(index_with_documents):
    index = await index_with_documents()
    update = await index.update_attributes_for_faceting(["genre"])
    await index.wait_for_pending_update(update.update_id)
    response = await index.search(
        "world", facet_filters=[["genre:action"]], attributes_to_retrieve=["title", "poster"]
    )
    assert len(response.hits) == 3
    assert response.facets_distribution is None
    assert response.exhaustive_facets_count is None
    assert "title" in response.hits[0]
    assert "poster" in response.hits[0]
    assert "overview" not in response.hits[0]
    assert "release_date" not in response.hits[0]
    assert response.hits[0]["title"] == "Avengers: Infinity War"
