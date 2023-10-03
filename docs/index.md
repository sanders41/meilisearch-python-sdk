# Meilisearch Python SDK

Meilisearch Python SDK provides both an async and sync client for the
[Meilisearch](https://github.com/meilisearch/meilisearch) API.

The focus of this documentation is on the Meilisearch Python SDK API. More information of
Meilisearch itself and how to use it can be found in [here](https://www.meilisearch.com/docs).

## Which client to chose

If the code base you are working with uses asyncio, for example if you are using
[FastAPI](https://fastapi.tiangolo.com/), chose the `AsyncClint` otherwise chose the `Client`.
The functionality of the two clients is the same, the difference being the `AsyncClient` provides
async methods and uses the `AsyncIndex`, which also provides async methods, while the `Client`
provides blocking methods and uses the `Index`, which also provides blocking methods.
