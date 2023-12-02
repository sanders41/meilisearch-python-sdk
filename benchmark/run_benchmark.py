from __future__ import annotations

import asyncio
import json
import random
from collections.abc import Sequence
from copy import deepcopy
from pathlib import Path
from statistics import fmean
from time import time

from meilisearch import Client as MeilisearchClient
from meilisearch.models.task import TaskInfo as MeiliTaskInfo
from rich.console import Console
from rich.progress import track

from meilisearch_python_sdk import AsyncClient, Client
from meilisearch_python_sdk.models.task import TaskInfo
from meilisearch_python_sdk.types import JsonDict, JsonMapping


def generate_data(add_records: int = 1000000) -> list[JsonDict]:
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
    client: AsyncClient, data: Sequence[JsonMapping]
) -> tuple[list[TaskInfo], float]:
    index = client.index("movies")
    start = time()
    tasks = await index.add_documents_in_batches(data, batch_size=1000)
    end = time()

    return tasks, (end - start)


def benchmark_sync_add_document_in_batches(
    client: Client, data: Sequence[JsonMapping]
) -> tuple[list[TaskInfo], float]:
    index = client.index("movies")
    start = time()
    tasks = index.add_documents_in_batches(data, batch_size=1000)
    end = time()

    return tasks, (end - start)


def benchmark_meili_add_documents_in_batches(
    client: MeilisearchClient, data: Sequence[JsonMapping]
) -> tuple[list[MeiliTaskInfo], float]:
    index = client.index("movies")
    start = time()
    tasks = index.add_documents_in_batches(data, batch_size=1000)  # type: ignore
    end = time()

    return tasks, (end - start)


async def run_async_batch_add_benchmark(data: Sequence[JsonMapping]) -> list[float]:
    times = []
    for _ in track(range(10), description="Running async add in batches benchmark..."):
        async with AsyncClient("http://127.0.0.1:7700", "masterKey") as client:
            index = client.index("movies")
            _, time_taken = await benchmark_async_add_document_in_batches(client, data)
            times.append(time_taken)
            task = await client.cancel_tasks()
            await client.wait_for_task(task.task_uid, timeout_in_ms=None)
            task = await index.delete()
            await client.wait_for_task(task.task_uid, timeout_in_ms=None)

    return times


async def run_async_search_benchmark(movies_sampled: list[str]) -> list[float]:
    times = []
    for _ in track(range(10), description="Running async multi search benchmark..."):
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


async def setup_index(data: Sequence[JsonMapping]) -> None:
    console = Console()
    with console.status("Preparing Meilisearch for tests..."):
        async with AsyncClient("http://127.0.0.1:7700", "masterKey") as client:
            index = await client.create_index("movies")
            tasks = await index.add_documents_in_batches(data, batch_size=1000)
            waits = [client.wait_for_task(x.task_uid, timeout_in_ms=None) for x in tasks]
            await asyncio.gather(*waits)


def run_sync_batch_add_benchmark(data: Sequence[JsonMapping]) -> list[float]:
    times = []
    for _ in track(range(10), description="Running sync add in batches benchmark..."):
        client = Client("http://127.0.0.1:7700", "masterKey")
        index = client.index("movies")
        _, time_taken = benchmark_sync_add_document_in_batches(client, data)
        times.append(time_taken)
        task = client.cancel_tasks(statuses=["enqueued,processing"])
        client.wait_for_task(task.task_uid, timeout_in_ms=600000)
        task = index.delete()
        client.wait_for_task(task.task_uid, timeout_in_ms=600000)

    return times


def run_sync_search_benchmark(movies_sampled: list[str]) -> list[float]:
    client = Client("http://127.0.0.1:7700", "masterKey")
    index = client.index("movies")
    times = []
    for _ in track(range(10), description="Running sync multi search benchmark..."):
        start = time()
        for movie in movies_sampled:
            index.search(movie)
        end = time()
        times.append(end - start)

    return times


def run_meili_batch_add_benchmark(data: Sequence[JsonMapping]) -> list[float]:
    times = []
    for _ in track(range(10), description="Running meili add in batches benchmark..."):
        client = MeilisearchClient("http://127.0.0.1:7700", "masterKey")
        index = client.index("movies")
        _, time_taken = benchmark_meili_add_documents_in_batches(client, data)
        times.append(time_taken)
        task = client.cancel_tasks({"statuses": "enqueued,processing"})
        client.wait_for_task(task.task_uid, timeout_in_ms=600000)
        task = index.delete()
        client.wait_for_task(task.task_uid, timeout_in_ms=600000)

    return times


def run_meili_search_benchmark(movies_sampled: list[str]) -> list[float]:
    client = MeilisearchClient("http://127.0.0.1:7700", "masterKey")
    index = client.index("movies")
    times = []
    for _ in track(range(10), description="Running meili multi search benchmark..."):
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
    meili_add_batches = run_meili_batch_add_benchmark(data)

    async_add_batches_mean = fmean(async_add_batches)
    sync_add_batches_mean = fmean(sync_add_batches)
    meili_add_batches_mean = fmean(meili_add_batches)

    print(async_add_batches_mean)  # noqa: T201
    print(sync_add_batches_mean)  # noqa: T201
    print(meili_add_batches_mean)  # noqa: T201

    await setup_index(data)
    movies_sampled = create_search_samples()
    async_search = await run_async_search_benchmark(movies_sampled)
    sync_search = run_sync_search_benchmark(movies_sampled)
    meili_search = run_sync_search_benchmark(movies_sampled)

    async_search_mean = fmean(async_search)
    sync_search_mean = fmean(sync_search)
    meili_search_mean = fmean(meili_search)

    print(async_search_mean)  # noqa: T201
    print(sync_search_mean)  # noqa: T201
    print(meili_search_mean)  # noqa: T201


if __name__ == "__main__":
    # Set the seed to 0 so that the same data is generated each time
    random.seed(0)

    asyncio.run(main())
