# Developer API

## `Client`

### Create a client with a context manager

This client runs in a context manager which ensures that everything is cleaned up after the use of
the client is done. To create a client:

```py
from milisearch-python-async import Client


async with Client("http://localhost:7700", "masterKey") as client:
    index = client.index("movies")
    ...
```

### Create a client without a context manager

It is also possible to call the client without using a context manager, but in doing so you will
need to make sure to do the cleanup yourself:

```py
from meilisearch-python-async import Client


try:
    client = Client("http://localhost:7700", "masterKey")
    ...
finally:
    await client.aclose()

```

::: meilisearch_python_async.Client
    :docstring:
    :members: __init__ aclose create_dump create_index delete_index_if_exists get_indexes get_index index get_all_stats get_dump_status get_or_create_index get_keys get_raw_index get_raw_indexes get_version health

## `Index`

::: meilisearch_python_async.index.Index
    :docstring:
    :members: __init__ delete delete_if_exists update fetch_info get_primary_key create get_all_update_status get_update_status wait_for_pending_update get_stats search get_document get_documents add_documents add_documents_auto_batch add_documents_in_batches add_documents_from_directory add_documents_from_directory_auto_batch add_documents_from_directory_in_batches add_documents_from_file add_documents_from_file_auto_batch add_documents_from_file_in_batches add_documents_from_raw_file update_documents update_documents_auto_batch update_documents_in_batches update_documents_from_directory update_documents_from_directory_auto_batch update_documents_from_directory_in_batches update_documents_from_file update_documents_from_file_auto_batch update_documents_from_file_in_batches update_documents_from_raw_file delete_document delete_documents delete_all_documents get_settings update_settings reset_settings get_ranking_rules update_ranking_rules reset_ranking_rules get_distinct_attribute update_distinct_attribute reset_distinct_attribute get_searchable_attributes update_searchable_attributes reset_searchable_attributes get_displayed_attributes update_displayed_attributes reset_displayed_attributes get_stop_words update_stop_words reset_stop_words get_synonyms update_synonyms reset_synonyms get_filterable_attributes update_filterable_attributes reset_filterable_attributes get_sortable_attributes update_sortable_attributes reset_sortable_attributes

## Decorators

::: meilisearch_python_async.decorators.status_check
    :docstring:
