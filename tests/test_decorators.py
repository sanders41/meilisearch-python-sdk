from uuid import uuid4

import pytest

from meilisearch_python_sdk.decorators import add_documments, async_add_documments


@pytest.mark.parametrize("batch_size, primary_key", [(None, None), (10, "alternate")])
def test_add_documents_with_client(batch_size, primary_key, client):
    index_name = str(uuid4())
    documents = []

    for i in range(50):
        documents.append({"id": i, "alternate": i, "title": f"Title {i}"})

    @add_documments(
        index_name=index_name,
        client=client,
        batch_size=batch_size,
        primary_key=primary_key,
        wait_for_task=True,
    )
    def tester():
        return documents

    tester()

    index = client.get_index(index_name)

    if primary_key:
        assert index.primary_key == primary_key

    result = index.get_documents(limit=50)
    assert result.results == documents


def test_add_documents_no_client_or_url():
    index_name = str(uuid4())
    documents = [{"id": 1, "title": "Title 1"}, {"id": 2, "title": "Title 2"}]

    @add_documments(index_name=index_name, wait_for_task=True)
    def tester():
        return documents

    with pytest.raises(ValueError):
        tester()


@pytest.mark.parametrize("batch_size, primary_key", [(None, None), (10, "alternate")])
async def test_async_add_documents(batch_size, primary_key, async_client):
    index_name = str(uuid4())
    documents = []

    for i in range(50):
        documents.append({"id": i, "alternate": i, "title": f"Title {i}"})

    @async_add_documments(
        index_name=index_name,
        async_client=async_client,
        batch_size=batch_size,
        primary_key=primary_key,
        wait_for_task=True,
    )
    async def tester():
        return documents

    await tester()

    index = await async_client.get_index(index_name)

    if primary_key:
        assert index.primary_key == primary_key

    result = await index.get_documents(limit=50)

    # order will be random since documents were added async so sort them first.
    assert sorted(result.results, key=lambda x: x["id"]) == documents


async def test_async_add_documents_no_client():
    index_name = str(uuid4())
    documents = [{"id": 1, "title": "Title 1"}, {"id": 2, "title": "Title 2"}]

    @async_add_documments(index_name=index_name, wait_for_task=True)
    async def tester():
        return documents

    with pytest.raises(ValueError):
        await tester()
