from __future__ import annotations

import asyncio
import json
import random
from copy import deepcopy
from pathlib import Path
from statistics import fmean
from time import time
from typing import Any

from meilisearch import Client
from meilisearch.models.task import TaskInfo as SyncTaskInfo
from rich.console import Console
from rich.progress import track

from meilisearch_python_async import AsyncClient
from meilisearch_python_async._task import async_cancel_tasks, async_wait_for_task
from meilisearch_python_async.models.task import TaskInfo as AsyncTaskInfo


def generate_data(add_records: int = 1000000) -> list[dict[str, Any]]:
    """Generate data for running the benchmark.

    Defaults to creating a json file with 1000000 documents.
    """
    small_movies = Path().absolute() / "datasets/small_movies.json"
    with open(small_movies) as f:
        data = json.load(f)

    updated = deepcopy(data)

    # Start at 10000 to not overlap any ids already in small_movies.json
    start = 10000
    end = (add_records - len(data)) + start
    max_record = len(data) - 1
    select = 0
    for i in track(range(start, end), description="Generating data..."):
        new = deepcopy(data[select])
        new["id"] = i
        updated.append(new)

        select += 1
        if select > max_record:
            select = 0

    return updated


def create_search_samples() -> list[str]:
    """Generate a random sample of movie names for running the search benchmark.

    The samples are generated with repetition, as we have just 30 movies in the dataset.
    """
    small_movies = Path().absolute() / "datasets/small_movies.json"
    data = []
    with open(small_movies) as f:
        data = json.load(f)

    # We want to search on titles of movies
    movie_names = [movie["title"] for movie in data]
    # Also consider lower case movie names for variety
    movie_names_lower = [movie.lower() for movie in movie_names]
    # Sample from both lists with repetition
    movies_for_sampling = movie_names + movie_names_lower
    movies_sampled = random.choices(movies_for_sampling, k=1000)
    return movies_sampled


async def benchmark_async_add_document_in_batches(
    client: AsyncClient, data: list[dict[str, Any]]
) -> tuple[list[AsyncTaskInfo], float]:
    index = client.index("movies")
    start = time()
    tasks = await index.add_documents_in_batches(data, batch_size=1000)
    end = time()

    return tasks, (end - start)


def benchmark_sync_add_documents_in_batches(
    client: Client, data: list[dict[str, Any]]
) -> tuple[list[SyncTaskInfo], float]:
    index = client.index("movies")
    start = time()
    tasks = index.add_documents_in_batches(data, batch_size=1000)
    end = time()

    return tasks, (end - start)


async def run_async_batch_add_benchmark(data: list[dict[str, Any]]) -> list[float]:
    times = []
    for _ in track(range(10), description="Running async add in batches benchmark..."):
        async with AsyncClient("http://127.0.0.1:7700", "masterKey") as client:
            index = client.index("movies")
            _, time_taken = await benchmark_async_add_document_in_batches(client, data)
            times.append(time_taken)
            task = await async_cancel_tasks(index.http_client)
            await async_wait_for_task(client.http_client, task.task_uid, timeout_in_ms=None)
            task = await index.delete()
            await async_wait_for_task(client.http_client, task.task_uid, timeout_in_ms=None)

    return times


async def run_async_search_benchmark(movies_sampled: list[str]) -> list[float]:
    times = []
    for _ in track(range(10), description="Running async multi function benchmark..."):
        async with AsyncClient("http://127.0.0.1:7700", "masterKey") as client:
            index = client.index("movies")
            searches = []
            for movie in movies_sampled:
                searches.append(index.search(movie))

            start = time()
            await asyncio.gather(*searches)
            end = time()
            times.append(end - start)

    return times


async def setup_index(data: list[dict[str, Any]]) -> None:
    console = Console()
    with console.status("Preparing Meilisearch for tests..."):
        async with AsyncClient("http://127.0.0.1:7700", "masterKey") as client:
            index = await client.create_index("movies")
            tasks = await index.add_documents_in_batches(data, batch_size=1000)
            waits = [
                async_wait_for_task(client.http_client, x.task_uid, timeout_in_ms=None)
                for x in tasks
            ]
            await asyncio.gather(*waits)


def run_sync_batch_add_benchmark(data: list[dict[str, Any]]) -> list[float]:
    times = []
    for _ in track(range(10), description="Running sync add in batches benchmark..."):
        client = Client("http://127.0.0.1:7700", "masterKey")
        index = client.index("movies")
        _, time_taken = benchmark_sync_add_documents_in_batches(client, data)
        times.append(time_taken)
        task = client.cancel_tasks({"statuses": "enqueued,processing"})
        client.wait_for_task(task.task_uid, timeout_in_ms=600000)
        task = index.delete()
        client.wait_for_task(task.task_uid, timeout_in_ms=600000)

    return times


def run_sync_search_benchmark(movies_sampled: list[str]) -> list[float]:
    client = Client("http://127.0.0.1:7700", "masterKey")
    index = client.index("movies")
    times = []
    for _ in track(range(10), description="Running sync multi function benchmark..."):
        start = time()
        for movie in movies_sampled:
            index.search(movie)
        end = time()
        times.append(end - start)

    return times


async def main() -> None:
    data = generate_data()
    async_add_batches = await run_async_batch_add_benchmark(data)
    sync_add_batches = run_sync_batch_add_benchmark(data)

    async_add_batches_mean = fmean(async_add_batches)
    sync_add_batches_mean = fmean(sync_add_batches)

    print(async_add_batches_mean)  # noqa: T201
    print(sync_add_batches_mean)  # noqa: T201

    await setup_index(data)
    movies_sampled = create_search_samples()
    async_search = await run_async_search_benchmark(movies_sampled)
    sync_search = run_sync_search_benchmark(movies_sampled)

    async_search_mean = fmean(async_search)
    sync_search_mean = fmean(sync_search)

    print(async_search_mean)  # noqa: T201
    print(sync_search_mean)  # noqa: T201


if __name__ == "__main__":
    # Set the seed to 0 so that the same data is generated each time
    random.seed(0)

    asyncio.run(main())
