from __future__ import annotations

from asyncio import sleep
from functools import wraps
from typing import Any, Callable

from meilisearch_python_async.index import Index


def status_check(index: Index) -> Callable:
    """Decorator that reports back if errors occur during an asyncronus MeiliSearch task.

    If MeiliSearch reports back an error somthing similar to the following will be printed:

    ```sh
    FAILED: [UpdateStatus(status='failed', update_id=0, update_type={'name': 'DocumentsAddition'},
    enqueued_at=datetime.datetime(2021, 9, 2, 22, 47, 42, 234902, tzinfo=datetime.timezone.utc),
    duration=0.0, processed_at=datetime.datetime(2021, 9, 2, 22, 47, 42, 236647,
    tzinfo=datetime.timezone.utc), error=None)]
    ```

    **Args:**

    * **index:** The Index instance used to generate the asyncornous task.

     Usage:

    ```py
    >>> from meilisearch_async_client import Client
    >>> from meilisearch_status_check_decorator import status_check
    >>> index = Client("http://localhost.com", "masterKey").index("movies")
    >>> @status_check(index=index)
    >>> async def_bad_insert():
    >>>     await index.add_documents(documents)
    >>> await index.aclose()
    ```
    """

    def decorator_status_check(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            initial_stats = await index.get_all_update_status()
            initial_status_count = 0 if not initial_stats else len(initial_stats)

            result = await func(*args, **kwargs)

            errors = False
            all_status = await index.get_all_update_status()

            while True:
                if not all_status or not [
                    x.status for x in all_status if x.status not in ["processed", "failed"]
                ]:
                    break

                await sleep(1)
                all_status = await index.get_all_update_status()

            if all_status:
                if len(all_status) == initial_status_count + 1:
                    status = all_status[-1:]
                    if status[0].status == "failed":
                        errors = True
                else:
                    status = all_status[initial_status_count:]
                    for s in status:
                        if s.status == "failed":
                            errors = True

            if errors:
                print(f"FAILED: {status}")  # noqa: T001

            return result

        return wrapper

    return decorator_status_check
