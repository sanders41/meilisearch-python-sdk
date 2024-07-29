from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from meilisearch_python_sdk import AsyncClient, AsyncIndex
from meilisearch_python_sdk.errors import MeilisearchApiError, MeilisearchCommunicationError
from meilisearch_python_sdk.models.documents import DocumentsInfo
from meilisearch_python_sdk.models.health import Health
from meilisearch_python_sdk.models.search import SearchParams, SearchResults
from meilisearch_python_sdk.models.task import TaskInfo


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    try:
        health = await client.health()
        if health.status != "available":
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The Meilisearch server is not available",
            )
    except MeilisearchCommunicationError as e:
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to connect to the Meilisearch server",
        ) from e
    yield
    await client.aclose()  # Shutdown the client when exiting the app


app = FastAPI(lifespan=lifespan)
client = AsyncClient("http://127.0.0.1:7700", "masterKey")


async def get_index() -> AsyncIndex:
    try:
        index = await client.get_index("movies")
    except MeilisearchApiError as e:
        if e.status_code == 404:  # If the index movies does not already exist create it
            index = await client.create_index("movies", primary_key="id")
        else:
            raise
    return index


@app.get("/health")
async def check_health() -> Health:
    return await client.health()


@app.get("/documents")
async def get_documents(index: Annotated[AsyncIndex, Depends(get_index)]) -> DocumentsInfo:
    return await index.get_documents()


@app.post("/documents")
async def add_documents(
    documents: list[dict[str, Any]], index: Annotated[AsyncIndex, Depends(get_index)]
) -> list[TaskInfo]:
    return await index.add_documents_in_batches(documents)


@app.post("/search")
async def search(
    search_params: SearchParams, index: Annotated[AsyncIndex, Depends(get_index)]
) -> SearchResults:
    params = search_params.model_dump()
    del params["index_uid"]
    return await index.search(**params)
