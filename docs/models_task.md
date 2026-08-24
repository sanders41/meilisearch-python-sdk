## Task Models

Meilisearch processes writes asynchronously, so methods that modify data return a `TaskInfo`
rather than the result of the write. The `task_uid` from that `TaskInfo` can be used to look up
a `TaskResult` to find out whether the write succeeded. Batches group the tasks Meilisearch
processed together.

## Task Models API

::: meilisearch_python_sdk.models.task

## Batch Models API

::: meilisearch_python_sdk.models.batch
