from uuid import uuid4

import pytest

from meilisearch_python_sdk.decorators import (
    ConnectionInfo,
    add_documents,
    async_add_documents,
)


@pytest.mark.parametrize("batch_size, primary_key", ((None, None), (10, "alternate")))
def test_add_documents_with_client(batch_size, primary_key, client, ssl_verify):
    index_name = str(uuid4())
    documents = []

    for i in range(50):
        documents.append({"id": i, "alternate": i, "title": f"Title {i}"})

    @add_documents(
        index_name=index_name,
        connection_info=client,
        batch_size=batch_size,
        primary_key=primary_key,
        wait_for_task=True,
        verify=ssl_verify,
    )
    def tester():
        return documents

    tester()

    index = client.get_index(index_name)

    if primary_key:
        assert index.primary_key == primary_key

    result = index.get_documents(limit=50)
    assert result.results == documents


@pytest.mark.parametrize("batch_size, primary_key", ((None, None), (10, "alternate")))
def test_add_documents_with_connection_info(
    batch_size, primary_key, client, base_url, master_key, ssl_verify
):
    index_name = str(uuid4())
    documents = []

    for i in range(50):
        documents.append({"id": i, "alternate": i, "title": f"Title {i}"})

    @add_documents(
        index_name=index_name,
        connection_info=ConnectionInfo(url=base_url, api_key=master_key),
        batch_size=batch_size,
        primary_key=primary_key,
        wait_for_task=True,
        verify=ssl_verify,
    )
    def tester():
        return documents

    tester()

    index = client.get_index(index_name)

    if primary_key:
        assert index.primary_key == primary_key

    result = index.get_documents(limit=50)
    assert result.results == documents


@pytest.mark.parametrize("batch_size, primary_key", ((None, None), (10, "alternate")))
async def test_async_add_documents_with_client(batch_size, primary_key, async_client):
    index_name = str(uuid4())
    documents = []

    for i in range(50):
        documents.append({"id": i, "alternate": i, "title": f"Title {i}"})

    @async_add_documents(
        index_name=index_name,
        connection_info=async_client,
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


@pytest.mark.parametrize("batch_size, primary_key", ((None, None), (10, "alternate")))
async def test_async_add_documents_with_connection_info(
    batch_size, primary_key, async_client, base_url, master_key, ssl_verify
):
    index_name = str(uuid4())
    documents = []

    for i in range(50):
        documents.append({"id": i, "alternate": i, "title": f"Title {i}"})

    @async_add_documents(
        index_name=index_name,
        connection_info=ConnectionInfo(url=base_url, api_key=master_key),
        batch_size=batch_size,
        primary_key=primary_key,
        wait_for_task=True,
        verify=ssl_verify,
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
