from __future__ import annotations

import json
from asyncio import gather, get_running_loop
from csv import DictReader
from datetime import datetime
from functools import partial
from pathlib import Path
from sys import getsizeof
from typing import Any, AsyncGenerator
from urllib.parse import urlencode

import aiofiles
from httpx import AsyncClient

from meilisearch_python_async._http_requests import HttpRequests
from meilisearch_python_async.errors import InvalidDocumentError, MeiliSearchError, PayloadTooLarge
from meilisearch_python_async.models.index import IndexStats
from meilisearch_python_async.models.search import SearchResults
from meilisearch_python_async.models.settings import MeiliSearchSettings
from meilisearch_python_async.models.task import TaskId, TaskStatus
from meilisearch_python_async.task import wait_for_task


class Index:
    """Index class gives access to all indexes routes and child routes.

    https://docs.meilisearch.com/reference/api/indexes.html
    """

    def __init__(
        self,
        http_client: AsyncClient,
        uid: str,
        primary_key: str | None = None,
        created_at: str | datetime | None = None,
        updated_at: str | datetime | None = None,
    ):
        """Class initializer.

        **Args:**

        * **http_client:** An instance of the AsyncClient. This automatically gets passed by the
            Client when creating and Index instance.
        * **uid:** The index's unique identifier.
        * **primary_key:** The primary key of the documents. Defaults to None.
        * **created_at:** The date and time the index was created. Defaults to None.
        * **updated_at:** The date and time the index was last updated. Defaults to None.
        """
        self.uid = uid
        self.primary_key = primary_key
        self.created_at: datetime | None = Index._iso_to_date_time(created_at)
        self.updated_at: datetime | None = Index._iso_to_date_time(updated_at)
        self._base_url = "indexes/"
        self._base_url_with_uid = f"{self._base_url}{self.uid}"
        self._documents_url = f"{self._base_url_with_uid}/documents"
        self._stats_url = f"{self._base_url_with_uid}/stats"
        self._settings_url = f"{self._base_url_with_uid}/settings"
        self.http_client = http_client
        self._http_requests = HttpRequests(http_client)

    def __str__(self) -> str:
        return f"{type(self).__name__}(uid={self.uid}, primary_key={self.primary_key}, created_at={self.created_at}, updated_at={self.updated_at})"

    def __repr__(self) -> str:
        return f"{type(self).__name__}(uid={self.uid!r}, primary_key={self.primary_key!r}, created_at={self.created_at!r}, updated_at={self.updated_at!r})"

    async def delete(self) -> TaskStatus:
        """Deletes the index.

        **Returns:** The details of the task status.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        **

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.delete()
        ```
        """
        url = f"{self._base_url_with_uid}"
        response = await self._http_requests.delete(url)
        return TaskStatus(**response.json())

    async def delete_if_exists(self) -> bool:
        """Delete the index if it already exists.

        **Returns:** True if the index was deleted or False if not.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.delete_if_exists()
        ```
        """
        response = await self.delete()
        status = await wait_for_task(self.http_client, response.uid)
        if status.status == "succeeded":
            return True

        return False

    async def update(self, primary_key: str) -> Index:
        """Update the index primary key.

        **Args:**

        * **primary_key:** The primary key of the documents.

        **Returns:** An instance of the Index with the updated information.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     updated_index = await index.update()
        ```
        """
        payload = {"primaryKey": primary_key}
        url = f"{self._base_url_with_uid}"
        response = await self._http_requests.put(url, payload)
        await wait_for_task(self.http_client, response.json()["uid"], timeout_in_ms=100000)
        index_response = await self._http_requests.get(f"{url}")
        self.primary_key = index_response.json()["primaryKey"]
        return self

    async def fetch_info(self) -> Index:
        """Gets the infromation about the index.

        **Returns:** An instance of the Index containing the retrieved information.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     index_info = await index.fetch_info()
        ```
        """
        url = f"{self._base_url_with_uid}"
        response = await self._http_requests.get(url)
        index_dict = response.json()
        self.primary_key = index_dict["primaryKey"]
        loop = get_running_loop()
        self.created_at = await loop.run_in_executor(
            None, partial(Index._iso_to_date_time, index_dict["createdAt"])
        )
        self.updated_at = await loop.run_in_executor(
            None, partial(Index._iso_to_date_time, index_dict["updatedAt"])
        )
        return self

    async def get_primary_key(self) -> str | None:
        """Get the primary key.

        **Returns:** The primary key for the documents in the index.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     primary_key = await index.get_primary_key()
        ```
        """
        info = await self.fetch_info()
        return info.primary_key

    @classmethod
    async def create(
        cls, http_client: AsyncClient, uid: str, primary_key: str | None = None
    ) -> Index:
        """Creates a new index.

        In general this method should not be used directly and instead the index should be created
        through the `Client`.

        **Args:**

        * **http_client:** An instance of the AsyncClient. This automatically gets passed by the
            Client when creating and Index instance.
        * **uid:** The index's unique identifier.
        * **primary_key:** The primary key of the documents. Defaults to None.

        **Returns:** An instance of Index containing the information of the newly created index.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = await index.create(client, "movies")
        ```
        """
        if not primary_key:
            payload = {"uid": uid}
        else:
            payload = {"primaryKey": primary_key, "uid": uid}

        url = "indexes"
        http_request = HttpRequests(http_client)
        response = await http_request.post(url, payload)
        await wait_for_task(http_client, response.json()["uid"], timeout_in_ms=100000)
        index_response = await http_request.get(f"{url}/{uid}")
        index_dict = index_response.json()
        return cls(
            http_client=http_client,
            uid=index_dict["uid"],
            primary_key=index_dict["primaryKey"],
            created_at=index_dict["createdAt"],
            updated_at=index_dict["updatedAt"],
        )

    async def get_stats(self) -> IndexStats:
        """Get stats of the index.

        **Returns:** Stats of the index.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     stats = await index.get_stats()
        ```
        """
        url = f"{self._stats_url}"
        response = await self._http_requests.get(url)

        return IndexStats(**response.json())

    async def search(
        self,
        query: str | None = None,
        *,
        offset: int = 0,
        limit: int = 20,
        filter: str | list[str | list[str]] | None = None,
        facets_distribution: list[str] | None = None,
        attributes_to_retrieve: list[str] = ["*"],
        attributes_to_crop: list[str] | None = None,
        crop_length: int = 200,
        attributes_to_highlight: list[str] | None = None,
        sort: list[str] | None = None,
        matches: bool = False,
    ) -> SearchResults:
        """Search the index.

        **Args:**

        * **query:** String containing the word(s) to search
        * **offset:** Number of documents to skip. Defaults to 0.
        * **limit:** Maximum number of documents returned. Defaults to 20.
        * **filter:** Filter queries by an attribute value. Defaults to None.
        * **facets_distribution:** Facets for which to retrieve the matching count. Defaults to None.
        * **attributes_to_retrieve:** Attributes to display in the returned documents.
            Defaults to ["*"].
        * **attributes_to_crop:** Attributes whose values have to be cropped. Defaults to None.
        * **crop_length:** Length used to crop field values. Defaults to 200.
        * **attributes_to_highlight:** Attributes whose values will contain highlighted matching terms.
            Defaults to None.
        * **sort:** Attributes by which to sort the results. Defaults to None.
        * **matches:** Defines whether an object that contains information about the matches should be
            returned or not. Defaults to False.

        **Returns:** Results of the search

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     search_results = await index.search("Tron")
        ```
        """
        body = {
            "q": query,
            "offset": offset,
            "limit": limit,
            "filter": filter,
            "facetsDistribution": facets_distribution,
            "attributesToRetrieve": attributes_to_retrieve,
            "attributesToCrop": attributes_to_crop,
            "cropLength": crop_length,
            "attributesToHighlight": attributes_to_highlight,
            "sort": sort,
            "matches": matches,
        }
        url = f"{self._base_url_with_uid}/search"
        response = await self._http_requests.post(url, body=body)

        return SearchResults(**response.json())

    async def get_document(self, document_id: str) -> dict:
        """Get one document with given document identifier.

        **Args:**

        * **document_id:** Unique identifier of the document.

        **Returns:** The document information

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     document = await index.get_document("1234")
        ```
        """
        url = f"{self._documents_url}/{document_id}"
        response = await self._http_requests.get(url)
        return response.json()

    async def get_documents(
        self, *, offset: int = 0, limit: int = 20, attributes_to_retrieve: list[str] | None = None
    ) -> list[dict[str, Any]] | None:
        """Get a batch documents from the index.

        **Args:**

        * **offset:** Number of documents to skip. Defaults to 0.
        * **limit:** Maximum number of documents returnedd. Defaults to 20.
        * **attributes_to_retrieve:** Document attributes to show. If this value is None then all
            attributes are retrieved. Defaults to None.

        **Returns:** A list of documents.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.


        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     documents = await index.get_documents()
        ```
        """
        parameters: dict[str, Any] = {
            "offset": offset,
            "limit": limit,
        }

        if attributes_to_retrieve:
            parameters["attributesToRetrieve"] = ",".join(attributes_to_retrieve)

        url = f"{self._documents_url}?{urlencode(parameters)}"
        response = await self._http_requests.get(url)

        if not response.json():
            return None

        return response.json()

    async def add_documents(self, documents: list[dict], primary_key: str | None = None) -> TaskId:
        """Add documents to the index.

        **Args:**

        * **documents:** List of documents.
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> >>> documents = [
        >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
        >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
        >>> ]
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.add_documents(documents)
        ```
        """
        url = f"{self._documents_url}"
        if primary_key:
            formatted_primary_key = urlencode({"primaryKey": primary_key})
            url = f"{url}?{formatted_primary_key}"

        response = await self._http_requests.post(url, documents)
        return TaskId(**response.json())

    async def add_documents_auto_batch(
        self,
        documents: list[dict],
        *,
        max_payload_size: int = 104857600,
        primary_key: str | None = None,
    ) -> list[TaskId]:
        """Automatically splits the documents into batches when adding.

        Each batch tries to fill the max_payload_size

        **Args:**

        * **documents:** List of documents.
        * **max_payload_size:** The maximum payload size in bytes. Defaults to 104857600 (100MB).
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.

        **Returns:** List of update ids to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.
            PayloadTooLarge: If the largest document is larget than the max_payload_size

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> >>> documents = [
        >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
        >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
        >>> ]
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.add_documents_auto_batch(documents)
        ```
        """
        task_ids = []
        async for batch in Index._generate_auto_batches(documents, max_payload_size):
            task_id = await self.add_documents(batch, primary_key)
            task_ids.append(task_id)

        return task_ids

    async def add_documents_in_batches(
        self, documents: list[dict], *, batch_size: int = 1000, primary_key: str | None = None
    ) -> list[TaskId]:
        """Adds documents in batches to reduce RAM usage with indexing.

        **Args:**

        * **documents:** List of documents.
        * **batch_size:** The number of documents that should be included in each batch.
            Defaults to 1000.
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.

        **Returns:** List of update ids to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> >>> documents = [
        >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
        >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
        >>> ]
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.add_documents_in_batches(documents)
        ```
        """
        task_ids: list[TaskId] = []

        async for document_batch in Index._batch(documents, batch_size):
            task_id = await self.add_documents(document_batch, primary_key)
            task_ids.append(task_id)

        return task_ids

    async def add_documents_from_directory(
        self,
        directory_path: Path | str,
        *,
        primary_key: str | None = None,
        document_type: str = "json",
        combine_documents: bool = True,
    ) -> list[TaskId]:
        """Load all json files from a directory and add the documents to the index.

        **Args:**

        * **directory_path:** Path to the directory that contains the json files.
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.
        * **document_type:** The type of document being added. Accepted types are json, csv, and
                ndjson. For csv files the first row of the document should be a header row contining
                the field names, and ever for should have a title.
        * **combine_documents:** If set to True this will combine the documents from all the files
            before indexing them. Defaults to True.

        **Returns:** Update id to track the action.

        **Raises:**

        * **InvalidDocumentError:** If the docucment is not a valid format for MeiliSarch.
        * **MeiliSearchError:** If the file path is not valid
        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from pathlib import Path
        >>> from meilisearch_async_client import Client
        >>> directory_path = Path("/path/to/directory/containing/files")
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.add_documents_from_directory(directory_path)
        ```
        """
        directory = Path(directory_path) if isinstance(directory_path, str) else directory_path

        if combine_documents:
            all_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await Index._load_documents_from_file(path)
                    all_documents.append(documents)

            Index._raise_on_no_documents(all_documents, document_type, directory_path)

            loop = get_running_loop()
            combined = await loop.run_in_executor(
                None, partial(Index._combine_documents, all_documents)
            )

            response = await self.add_documents(combined, primary_key)
            return [response]

        add_documents = []
        for path in directory.iterdir():
            if path.suffix == f".{document_type}":
                documents = await Index._load_documents_from_file(path)
                add_documents.append(self.add_documents(documents, primary_key))

        Index._raise_on_no_documents(add_documents, document_type, directory_path)

        if len(add_documents) > 1:
            # Send the first document on its own before starting the gather. Otherwise MeiliSearch
            # returns an error because it thinks all entries are trying to create the same index.
            first_response = [await add_documents.pop()]
            responses = await gather(*add_documents)
            responses = [*first_response, *responses]
        else:
            responses = [await add_documents[0]]

        return responses

    async def add_documents_from_directory_auto_batch(
        self,
        directory_path: Path | str,
        *,
        max_payload_size: int = 104857600,
        primary_key: str | None = None,
        document_type: str = "json",
        combine_documents: bool = True,
    ) -> list[TaskId]:
        """Load all json files from a directory and add the documents to the index.

        Documents are automatically split into batches as large as possible based on the max payload
        size.

        **Args:**

        * **directory_path:** Path to the directory that contains the json files.
        * **max_payload_size:** The maximum payload size in bytes. Defaults to 104857600.
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.
        * **document_type:** The type of document being added. Accepted types are json, csv, and
                ndjson. For csv files the first row of the document should be a header row contining
                the field names, and ever for should have a title.
        * **combine_documents:** If set to True this will combine the documents from all the files
            before indexing them. Defaults to True.

        **Returns:** List of update ids to track the action.

        **Raises:**

        * **InvalidDocumentError:** If the docucment is not a valid format for MeiliSarch.
        * **MeiliSearchError:** If the file path is not valid
        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from pathlib import Path
        >>> from meilisearch_async_client import Client
        >>> directory_path = Path("/path/to/directory/containing/files")
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.add_documents_from_directory_auto_batch(directory_path)
        ```
        """
        directory = Path(directory_path) if isinstance(directory_path, str) else directory_path

        if combine_documents:
            all_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await Index._load_documents_from_file(path)
                    all_documents.append(documents)

            Index._raise_on_no_documents(all_documents, document_type, directory_path)

            loop = get_running_loop()
            combined = await loop.run_in_executor(
                None, partial(Index._combine_documents, all_documents)
            )

            return await self.add_documents_auto_batch(
                combined, max_payload_size=max_payload_size, primary_key=primary_key
            )

        responses: list[TaskId] = []

        add_documents = []
        for path in directory.iterdir():
            if path.suffix == f".{document_type}":
                documents = await Index._load_documents_from_file(path)
                add_documents.append(
                    self.add_documents_auto_batch(
                        documents, max_payload_size=max_payload_size, primary_key=primary_key
                    )
                )

        Index._raise_on_no_documents(add_documents, document_type, directory_path)

        if len(add_documents) > 1:
            # Send the first document on its own before starting the gather. Otherwise MeiliSearch
            # returns an error because it thinks all entries are trying to create the same index.
            first_response = await add_documents.pop()
            responses_gather = await gather(*add_documents)
            responses = [*first_response, *[x for y in responses_gather for x in y]]
        else:
            responses = await add_documents[0]

        return responses

    async def add_documents_from_directory_in_batches(
        self,
        directory_path: Path | str,
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
        document_type: str = "json",
        combine_documents: bool = True,
    ) -> list[TaskId]:
        """Load all json files from a directory and add the documents to the index in batches.

        **Args:**

        * **directory_path:** Path to the directory that contains the json files.
        * **batch_size:** The number of documents that should be included in each batch.
            Defaults to 1000.
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.
        * **document_type:** The type of document being added. Accepted types are json, csv, and
            ndjson. For csv files the first row of the document should be a header row contining
            the field names, and ever for should have a title.
        * **combine_documents:** If set to True this will combine the documents from all the files
            before indexing them. Defaults to True.

        **Returns:** List of update ids to track the action.

        **Raises:**

        * **InvalidDocumentError:** If the docucment is not a valid format for MeiliSarch.
        * **MeiliSearchError:** If the file path is not valid
        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from pathlib import Path
        >>> from meilisearch_async_client import Client
        >>> directory_path = Path("/path/to/directory/containing/files")
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.add_documents_from_directory_in_batches(directory_path)
        ```
        """
        directory = Path(directory_path) if isinstance(directory_path, str) else directory_path

        if combine_documents:
            all_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await Index._load_documents_from_file(path)
                    all_documents.append(documents)

            Index._raise_on_no_documents(all_documents, document_type, directory_path)

            loop = get_running_loop()
            combined = await loop.run_in_executor(
                None, partial(Index._combine_documents, all_documents)
            )

            return await self.add_documents_in_batches(
                combined, batch_size=batch_size, primary_key=primary_key
            )

        responses: list[TaskId] = []

        add_documents = []
        for path in directory.iterdir():
            if path.suffix == f".{document_type}":
                documents = await Index._load_documents_from_file(path)
                add_documents.append(
                    self.add_documents_in_batches(
                        documents, batch_size=batch_size, primary_key=primary_key
                    )
                )

        Index._raise_on_no_documents(add_documents, document_type, directory_path)

        if len(add_documents) > 1:
            # Send the first document on its own before starting the gather. Otherwise MeiliSearch
            # returns an error because it thinks all entries are trying to create the same index.
            first_response = await add_documents.pop()
            responses_gather = await gather(*add_documents)
            responses = [*first_response, *[x for y in responses_gather for x in y]]
        else:
            responses = await add_documents[0]

        return responses

    async def add_documents_from_file(
        self, file_path: Path | str, primary_key: str | None = None
    ) -> TaskId:
        """Add documents to the index from a json file.

        **Args:**

        * **file_path:** Path to the json file.
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.

        **Returns:** Update id to track the action.

        **Raises:**

        * **InvalidDocumentError:** If the docucment is not a valid format for MeiliSarch.
        * **MeiliSearchError:** If the file path is not valid
        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from pathlib import Path
        >>> from meilisearch_async_client import Client
        >>> file_path = Path("/path/to/file.json")
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.add_documents_from_file(file_path)
        ```
        """
        documents = await Index._load_documents_from_file(file_path)

        return await self.add_documents(documents, primary_key=primary_key)

    async def add_documents_from_file_auto_batch(
        self,
        file_path: Path | str,
        *,
        max_payload_size: int = 104857600,
        primary_key: str | None = None,
    ) -> list[TaskId]:
        """Automatically splits the documents into batches when adding from a json file.

        Each batch tries to fill the max_payload_size

        **Args:**

        * **file_path:** Path to the json file.
        * **max_payload_size:** The maximum payload size in bytes. Defaults to 104857600 (100MB).
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.

        **Returns:** List of update ids to track the action.

        **Raises:**

        * **InvalidDocumentError:** If the docucment is not a valid format for MeiliSarch.
        * **MeiliSearchError:** If the file path is not valid.
        * **MeiliSearchCommunicationError:** If there was an error communicating with the server.
        * **MeiliSearchApiError:** If the MeiliSearch API returned an error.
        * **PayloadTooLarge:** If the largest document is larget than the max_payload_size

        Usage:

        ```py
        >>> from pathlib import Path
        >>> from meilisearch_async_client import Client
        >>> file_path = Path("/path/to/file.json")
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.add_documents_from_file_auto_batch(file_path)
        ```
        """
        documents = await Index._load_documents_from_file(file_path)

        task_ids = []
        async for batch in Index._generate_auto_batches(documents, max_payload_size):
            task_id = await self.add_documents(batch, primary_key)
            task_ids.append(task_id)

        return task_ids

    async def add_documents_from_file_in_batches(
        self, file_path: Path | str, *, batch_size: int = 1000, primary_key: str | None = None
    ) -> list[TaskId]:
        """Adds documents form a json file in batches to reduce RAM usage with indexing.

        **Args:**

        * **file_path:** Path to the json file.
        * **batch_size:** The number of documents that should be included in each batch.
            Defaults to 1000.
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.

        **Returns:** List of update ids to track the action.

        **Raises:**

        * **InvalidDocumentError:** If the docucment is not a valid format for MeiliSarch.
        * **MeiliSearchError:** If the file path is not valid
        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from pathlib import Path
        >>> from meilisearch_async_client import Client
        >>> file_path = Path("/path/to/file.json")
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.add_documents_from_file_in_batches(file_path)
        ```
        """
        documents = await Index._load_documents_from_file(file_path)

        return await self.add_documents_in_batches(
            documents, batch_size=batch_size, primary_key=primary_key
        )

    async def add_documents_from_raw_file(
        self, file_path: Path | str, primary_key: str | None = None
    ) -> TaskId:
        """Directly send csv or ndjson files to MeiliSearch without pre-processing.

        The can reduce RAM usage from MeiliSearch during indexing, but does not include the option
        for batching.

        **Args:**

        * **file_path:** The path to the file to send to MeiliSearch. Only csv and ndjson files are
            allowed.
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.

        **Returns:** Update id to track the action.

        **Raises:**

        * **ValueError:** If the file is not a csv or ndjson file.
        * **MeiliSearchError:** If the file path is not valid
        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from pathlib import Path
        >>> from meilisearch_async_client import Client
        >>> file_path = Path("/path/to/file.csv")
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.add_documents_from_raw_file(file_path)
        ```
        """
        upload_path = Path(file_path) if isinstance(file_path, str) else file_path
        if not upload_path.exists():
            raise MeiliSearchError("No file found at the specified path")

        if upload_path.suffix not in (".csv", ".ndjson"):
            raise ValueError("Only csv and ndjson files can be sent as binary files")

        content_type = "text/csv" if upload_path.suffix == ".csv" else "application/x-ndjson"
        url = self._documents_url
        if primary_key:
            formatted_primary_key = urlencode({"primaryKey": primary_key})
            url = f"{url}?{formatted_primary_key}"

        async with aiofiles.open(upload_path, "r") as f:
            data = await f.read()

        response = await self._http_requests.post(url, body=data, content_type=content_type)

        return TaskId(**response.json())

    async def update_documents(
        self, documents: list[dict], primary_key: str | None = None
    ) -> TaskId:
        """Update documents in the index.

        **Args:**

        * **documents:** List of documents.
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> documents = [
        >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
        >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
        >>> ]
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_documents(documents)
        ```
        """
        url = f"{self._documents_url}"
        if primary_key:
            formatted_primary_key = urlencode({"primaryKey": primary_key})
            url = f"{url}?{formatted_primary_key}"

        response = await self._http_requests.put(url, documents)
        return TaskId(**response.json())

    async def update_documents_auto_batch(
        self,
        documents: list[dict],
        *,
        max_payload_size: int = 104857600,
        primary_key: str | None = None,
    ) -> list[TaskId]:
        """Automatically splits the documents into batches when updating.

        Each batch tries to fill the max_payload_size

        **Args:**

        * **documents:** List of documents.
        * **max_payload_size:** The maximum payload size in bytes. Defaults to 104857600 (100MB).
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.

        **Returns:** List of update ids to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.
            PayloadTooLarge: If the largest document is larget than the max_payload_size

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> documents = [
        >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
        >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
        >>> ]
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_documents_auto_batch(documents)
        ```
        """
        task_ids = []
        async for batch in Index._generate_auto_batches(documents, max_payload_size):
            task_id = await self.update_documents(batch, primary_key)
            task_ids.append(task_id)

        return task_ids

    async def update_documents_in_batches(
        self, documents: list[dict], *, batch_size: int = 1000, primary_key: str | None = None
    ) -> list[TaskId]:
        """Update documents in batches to reduce RAM usage with indexing.

        Each batch tries to fill the max_payload_size

        **Args:**

        * **documents:** List of documents.
        * **batch_size:** The number of documents that should be included in each batch.
            Defaults to 1000.
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.

        **Returns:** List of update ids to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> documents = [
        >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
        >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
        >>> ]
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_documents_in_batches(documents)
        ```
        """
        task_ids: list[TaskId] = []

        async for document_batch in Index._batch(documents, batch_size):
            task_id = await self.update_documents(document_batch, primary_key)
            task_ids.append(task_id)

        return task_ids

    async def update_documents_from_directory(
        self,
        directory_path: Path | str,
        *,
        primary_key: str | None = None,
        document_type: str = "json",
        combine_documents: bool = True,
    ) -> list[TaskId]:
        """Load all json files from a directory and update the documents.

        **Args:**

        * **directory_path:** Path to the directory that contains the json files.
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.
        * **document_type:** The type of document being added. Accepted types are json, csv, and
                ndjson. For csv files the first row of the document should be a header row contining
                the field names, and ever for should have a title.
        * **combine_documents:** If set to True this will combine the documents from all the files
            before indexing them. Defaults to True.

        **Returns:** Update id to track the action.

        **Raises:**

        * **InvalidDocumentError:** If the docucment is not a valid format for MeiliSarch.
        * **MeiliSearchError:** If the file path is not valid
        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from pathlib import Path
        >>> from meilisearch_async_client import Client
        >>> directory_path = Path("/path/to/directory/containing/files")
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_documents_from_directory(directory_path)
        ```
        """
        directory = Path(directory_path) if isinstance(directory_path, str) else directory_path

        if combine_documents:
            all_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await Index._load_documents_from_file(path)
                    all_documents.append(documents)

            Index._raise_on_no_documents(all_documents, document_type, directory_path)

            loop = get_running_loop()
            combined = await loop.run_in_executor(
                None, partial(Index._combine_documents, all_documents)
            )

            response = await self.update_documents(combined, primary_key)
            return [response]

        update_documents = []
        for path in directory.iterdir():
            if path.suffix == f".{document_type}":
                documents = await Index._load_documents_from_file(path)
                update_documents.append(self.update_documents(documents, primary_key))

        Index._raise_on_no_documents(update_documents, document_type, directory_path)

        if len(update_documents) > 1:
            # Send the first document on its own before starting the gather. Otherwise MeiliSearch
            # returns an error because it thinks all entries are trying to create the same index.
            first_response = [await update_documents.pop()]
            responses = await gather(*update_documents)
            responses = [*first_response, *responses]
        else:
            responses = [await update_documents[0]]

        return responses

    async def update_documents_from_directory_auto_batch(
        self,
        directory_path: Path | str,
        *,
        max_payload_size: int = 104857600,
        primary_key: str | None = None,
        document_type: str = "json",
        combine_documents: bool = True,
    ) -> list[TaskId]:
        """Load all json files from a directory and update the documents.

        Documents are automatically split into batches as large as possible based on the max payload
        size.

        **Args:**

        * **directory_path:** Path to the directory that contains the json files.
        * **max_payload_size:** The maximum payload size in bytes. Defaults to 104857600.
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.
        * **document_type:** The type of document being added. Accepted types are json, csv, and
                ndjson. For csv files the first row of the document should be a header row contining
                the field names, and ever for should have a title.
        * **combine_documents:** If set to True this will combine the documents from all the files
            before indexing them. Defaults to True.

        **Returns:** List of update ids to track the action.

        **Raises:**

        * **InvalidDocumentError:** If the docucment is not a valid format for MeiliSarch.
        * **MeiliSearchError:** If the file path is not valid
        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from pathlib import Path
        >>> from meilisearch_async_client import Client
        >>> directory_path = Path("/path/to/directory/containing/files")
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_documents_from_directory_auto_batch(directory_path)
        ```
        """
        directory = Path(directory_path) if isinstance(directory_path, str) else directory_path

        if combine_documents:
            all_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await Index._load_documents_from_file(path)
                    all_documents.append(documents)

            Index._raise_on_no_documents(all_documents, document_type, directory_path)

            loop = get_running_loop()
            combined = await loop.run_in_executor(
                None, partial(Index._combine_documents, all_documents)
            )

            return await self.update_documents_auto_batch(
                combined, max_payload_size=max_payload_size, primary_key=primary_key
            )

        update_documents = []
        for path in directory.iterdir():
            if path.suffix == f".{document_type}":
                documents = await Index._load_documents_from_file(path)
                update_documents.append(
                    self.update_documents_auto_batch(
                        documents, max_payload_size=max_payload_size, primary_key=primary_key
                    )
                )

        Index._raise_on_no_documents(update_documents, document_type, directory_path)

        if len(update_documents) > 1:
            # Send the first document on its own before starting the gather. Otherwise MeiliSearch
            # returns an error because it thinks all entries are trying to create the same index.
            first_response = await update_documents.pop()
            responses = await gather(*update_documents)
            responses = [*first_response, *[x for y in responses for x in y]]
        else:
            responses = await update_documents[0]

        return responses

    async def update_documents_from_directory_in_batches(
        self,
        directory_path: Path | str,
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
        document_type: str = "json",
        combine_documents: bool = True,
    ) -> list[TaskId]:
        """Load all json files from a directory and update the documents.

        **Args:**

        * **directory_path:** Path to the directory that contains the json files.
        * **batch_size:** The number of documents that should be included in each batch.
            Defaults to 1000.
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.
        * **document_type:** The type of document being added. Accepted types are json, csv, and
                ndjson. For csv files the first row of the document should be a header row contining
                the field names, and ever for should have a title.
        * **combine_documents:** If set to True this will combine the documents from all the files
            before indexing them. Defaults to True.

        **Returns:** List of update ids to track the action.

        **Raises:**

        * **InvalidDocumentError:** If the docucment is not a valid format for MeiliSarch.
        * **MeiliSearchError:** If the file path is not valid
        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from pathlib import Path
        >>> from meilisearch_async_client import Client
        >>> directory_path = Path("/path/to/directory/containing/files")
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_documents_from_directory_in_batches(directory_path)
        ```
        """
        directory = Path(directory_path) if isinstance(directory_path, str) else directory_path

        if combine_documents:
            all_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await Index._load_documents_from_file(path)
                    all_documents.append(documents)

            Index._raise_on_no_documents(all_documents, document_type, directory_path)

            loop = get_running_loop()
            combined = await loop.run_in_executor(
                None, partial(Index._combine_documents, all_documents)
            )

            return await self.update_documents_in_batches(
                combined, batch_size=batch_size, primary_key=primary_key
            )

        responses: list[TaskId] = []

        update_documents = []
        for path in directory.iterdir():
            if path.suffix == f".{document_type}":
                documents = await Index._load_documents_from_file(path)
                update_documents.append(
                    self.update_documents_in_batches(
                        documents, batch_size=batch_size, primary_key=primary_key
                    )
                )

        Index._raise_on_no_documents(update_documents, document_type, directory_path)

        if len(update_documents) > 1:
            # Send the first document on its own before starting the gather. Otherwise MeiliSearch
            # returns an error because it thinks all entries are trying to create the same index.
            first_response = await update_documents.pop()
            responses_gather = await gather(*update_documents)
            responses = [*first_response, *[x for y in responses_gather for x in y]]
        else:
            responses = await update_documents[0]

        return responses

    async def update_documents_from_file(
        self, file_path: Path | str, primary_key: str | None = None
    ) -> TaskId:
        """Add documents in the index from a json file.

        **Args:**

        * **file_path:** Path to the json file.
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from pathlib import Path
        >>> from meilisearch_async_client import Client
        >>> file_path = Path("/path/to/file.json")
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_documents_from_file(file_path)
        ```
        """
        documents = await Index._load_documents_from_file(file_path)

        return await self.update_documents(documents, primary_key=primary_key)

    async def update_documents_from_file_auto_batch(
        self,
        file_path: Path | str,
        *,
        max_payload_size: int = 104857600,
        primary_key: str | None = None,
    ) -> list[TaskId]:
        """Automatically splits the documents into batches when updating from a json file.

        Each batch tries to fill the max_payload_size

        **Args:**

        * **file_path:** Path to the json file.
        * **batch_size:** The number of documents that should be included in each batch.
            Defaults to 1000.
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.

        **Returns:** List of update ids to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from pathlib import Path
        >>> from meilisearch_async_client import Client
        >>> file_path = Path("/path/to/file.json")
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_documents_from_file_auto_batch(file_path)
        ```
        """
        documents = await Index._load_documents_from_file(file_path)

        task_ids = []
        async for batch in Index._generate_auto_batches(documents, max_payload_size):
            task_id = await self.update_documents(batch, primary_key)
            task_ids.append(task_id)

        return task_ids

    async def update_documents_from_file_in_batches(
        self, file_path: Path | str, *, batch_size: int = 1000, primary_key: str | None = None
    ) -> list[TaskId]:
        """Updates documents form a json file in batches to reduce RAM usage with indexing.

        **Args:**

        * **file_path:** Path to the json file.
        * **batch_size:** The number of documents that should be included in each batch.
            Defaults to 1000.
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.

        **Returns:** List of update ids to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from pathlib import Path
        >>> from meilisearch_async_client import Client
        >>> file_path = Path("/path/to/file.json")
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_documents_from_file_in_batches(file_path)
        ```
        """
        documents = await Index._load_documents_from_file(file_path)

        return await self.update_documents_in_batches(
            documents, batch_size=batch_size, primary_key=primary_key
        )

    async def update_documents_from_raw_file(
        self, file_path: Path | str, primary_key: str | None = None
    ) -> TaskId:
        """Directly send csv or ndjson files to MeiliSearch without pre-processing.

        The can reduce RAM usage from MeiliSearch during indexing, but does not include the option
        for batching.

        **Args:**

        * **file_path:** The path to the file to send to MeiliSearch. Only csv and ndjson files are
            allowed.
        * **primary_key:** The primary key of the documents. This will be ignored if already set.
            Defaults to None.

        **Returns:** Update id to track the action.

        **Raises:**

        * **ValueError:** If the file is not a csv or ndjson file.
        * **MeiliSearchError:** If the file path is not valid
        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from pathlib import Path
        >>> from meilisearch_async_client import Client
        >>> file_path = Path("/path/to/file.csv")
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_documents_from_raw_file(file_path)
        ```
        """
        upload_path = Path(file_path) if isinstance(file_path, str) else file_path
        if not upload_path.exists():
            raise MeiliSearchError("No file found at the specified path")

        if upload_path.suffix not in (".csv", ".ndjson"):
            raise ValueError("Only csv and ndjson files can be sent as binary files")

        content_type = "text/csv" if upload_path.suffix == ".csv" else "application/x-ndjson"
        url = self._documents_url
        if primary_key:
            formatted_primary_key = urlencode({"primaryKey": primary_key})
            url = f"{url}?{formatted_primary_key}"

        async with aiofiles.open(upload_path, "r") as f:
            data = await f.read()

        response = await self._http_requests.put(url, body=data, content_type=content_type)

        return TaskId(**response.json())

    async def delete_document(self, document_id: str) -> TaskId:
        """Delete one document from the index.

        **Args:**

        * **document_id:** Unique identifier of the document.

        **Returns:** Update id to track the action.

        **Rases:**

        * **MeiliSearchCommunicationError:** If there was an error communicating with the server.
        * **MeiliSearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.delete_document("1234")
        ```
        """
        url = f"{self._documents_url}/{document_id}"
        response = await self._http_requests.delete(url)

        return TaskId(**response.json())

    async def delete_documents(self, ids: list[str]) -> TaskId:
        """Delete multiple documents from the index.

        **Args:**

        * **ids:** List of unique identifiers of documents.

        **Returns:** List of update ids to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.delete_documents(["1234", "5678"])
        ```
        """
        url = f"{self._documents_url}/delete-batch"
        response = await self._http_requests.post(url, ids)

        return TaskId(**response.json())

    async def delete_all_documents(self) -> TaskId:
        """Delete all documents from the index.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.delete_all_document()
        ```
        """
        url = f"{self._documents_url}"
        response = await self._http_requests.delete(url)

        return TaskId(**response.json())

    async def get_settings(self) -> MeiliSearchSettings:
        """Get settings of the index.

        **Returns:** Settings of the index.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     settings = await index.get_settings()
        ```
        """
        url = f"{self._settings_url}"
        response = await self._http_requests.get(url)

        return MeiliSearchSettings(**response.json())

    async def update_settings(self, body: MeiliSearchSettings) -> TaskId:
        """Update settings of the index.

        **Args:**

        * **body:** Settings of the index.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> from meilisearch_async_client import MeiliSearchSettings
        >>> new_settings = MeiliSearchSettings(
        >>>     synonyms={"wolverine": ["xmen", "logan"], "logan": ["wolverine"]},
        >>>     stop_words=["the", "a", "an"],
        >>>     ranking_rules=[
        >>>         "words",
        >>>         "typo",
        >>>         "proximity",
        >>>         "attribute",
        >>>         "sort",
        >>>         "exactness",
        >>>         "release_date:desc",
        >>>         "rank:desc",
        >>>    ],
        >>>    filterable_attributes=["genre", "director"],
        >>>    distinct_attribute="url",
        >>>    searchable_attributes=["title", "description", "genre"],
        >>>    displayed_attributes=["title", "description", "genre", "release_date"],
        >>>    sortable_attributes=["title", "release_date"],
        >>> )
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_settings(new_settings)
        ```
        """
        body_dict = {k: v for k, v in body.dict(by_alias=True).items() if v is not None}

        url = f"{self._settings_url}"
        response = await self._http_requests.post(url, body_dict)

        return TaskId(**response.json())

    async def reset_settings(self) -> TaskId:
        """Reset settings of the index to default values.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.reset_settings()
        ```
        """
        url = f"{self._settings_url}"
        response = await self._http_requests.delete(url)

        return TaskId(**response.json())

    async def get_ranking_rules(self) -> list[str]:
        """Get ranking rules of the index.

        **Returns:** List containing the ranking rules of the index.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     ranking_rules = await index.get_ranking_rules()
        ```
        """
        url = f"{self._settings_url}/ranking-rules"
        response = await self._http_requests.get(url)

        return response.json()

    async def update_ranking_rules(self, ranking_rules: list[str]) -> TaskId:
        """Update ranking rules of the index.

        **Args:**

        * **ranking_rules:** List containing the ranking rules.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> ranking_rules=[
        >>>      "words",
        >>>      "typo",
        >>>      "proximity",
        >>>      "attribute",
        >>>      "sort",
        >>>      "exactness",
        >>>      "release_date:desc",
        >>>      "rank:desc",
        >>> ],
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_ranking_rules(ranking_rules)
        ```
        """
        url = f"{self._settings_url}/ranking-rules"
        respose = await self._http_requests.post(url, ranking_rules)

        return TaskId(**respose.json())

    async def reset_ranking_rules(self) -> TaskId:
        """Reset ranking rules of the index to default values.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.reset_ranking_rules()
        ```
        """
        url = f"{self._settings_url}/ranking-rules"
        response = await self._http_requests.delete(url)

        return TaskId(**response.json())

    async def get_distinct_attribute(self) -> str | None:
        """Get distinct attribute of the index.

        **Returns:** String containing the distinct attribute of the index. If no distinct attribute
            `None` is returned.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     distinct_attribute = await index.get_distinct_attribute()
        ```
        """
        url = f"{self._settings_url}/distinct-attribute"
        response = await self._http_requests.get(url)

        if not response.json():
            None

        return response.json()

    async def update_distinct_attribute(self, body: str) -> TaskId:
        """Update distinct attribute of the index.

        **Args:**

        * **body:** Distinct attribute.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_distinct_attribute("url")
        ```
        """
        url = f"{self._settings_url}/distinct-attribute"
        response = await self._http_requests.post(url, body)

        return TaskId(**response.json())

    async def reset_distinct_attribute(self) -> TaskId:
        """Reset distinct attribute of the index to default values.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.reset_distinct_attributes()
        ```
        """
        url = f"{self._settings_url}/distinct-attribute"
        response = await self._http_requests.delete(url)

        return TaskId(**response.json())

    async def get_searchable_attributes(self) -> list[str]:
        """Get searchable attributes of the index.

        **Returns:** List containing the searchable attributes of the index.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     searchable_attributes = await index.get_searchable_attributes()
        ```
        """
        url = f"{self._settings_url}/searchable-attributes"
        response = await self._http_requests.get(url)
        return response.json()

    async def update_searchable_attributes(self, body: list[str]) -> TaskId:
        """Update searchable attributes of the index.

        **Args:**

        * **body:** List containing the searchable attributes.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_searchable_attributes(["title", "description", "genre"])
        ```
        """
        url = f"{self._settings_url}/searchable-attributes"
        response = await self._http_requests.post(url, body)

        return TaskId(**response.json())

    async def reset_searchable_attributes(self) -> TaskId:
        """Reset searchable attributes of the index to default values.

        **Args:**

        * **body:** List containing the searchable attributes.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.reset_searchable_attributes()
        ```
        """
        url = f"{self._settings_url}/searchable-attributes"
        response = await self._http_requests.delete(url)

        return TaskId(**response.json())

    async def get_displayed_attributes(self) -> list[str]:
        """Get displayed attributes of the index.

        **Returns:** List containing the displayed attributes of the index.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     displayed_attributes = await index.get_displayed_attributes()
        ```
        """
        url = f"{self._settings_url}/displayed-attributes"
        response = await self._http_requests.get(url)
        return response.json()

    async def update_displayed_attributes(self, body: list[str]) -> TaskId:
        """Update displayed attributes of the index.

        **Args:**

        * **body:** List containing the displayed attributes.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_displayed_attributes(
        >>>         ["title", "description", "genre", "release_date"]
        >>>     )
        ```
        """
        url = f"{self._settings_url}/displayed-attributes"
        response = await self._http_requests.post(url, body)

        return TaskId(**response.json())

    async def reset_displayed_attributes(self) -> TaskId:
        """Reset displayed attributes of the index to default values.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.reset_displayed_attributes()
        ```
        """
        url = f"{self._settings_url}/displayed-attributes"
        response = await self._http_requests.delete(url)

        return TaskId(**response.json())

    async def get_stop_words(self) -> list[str] | None:
        """Get stop words of the index.

        **Returns:** List containing the stop words of the index.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     stop_words = await index.get_stop_words()
        ```
        """
        url = f"{self._settings_url}/stop-words"
        response = await self._http_requests.get(url)

        if not response.json():
            return None

        return response.json()

    async def update_stop_words(self, body: list[str]) -> TaskId:
        """Update stop words of the index.

        **Args:**

        * **body:** List containing the stop words of the index.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_stop_words(["the", "a", "an"])
        ```
        """
        url = f"{self._settings_url}/stop-words"
        response = await self._http_requests.post(url, body)

        return TaskId(**response.json())

    async def reset_stop_words(self) -> TaskId:
        """Reset stop words of the index to default values.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.reset_stop_words()
        ```
        """
        url = f"{self._settings_url}/stop-words"
        response = await self._http_requests.delete(url)

        return TaskId(**response.json())

    async def get_synonyms(self) -> dict[str, list[str]] | None:
        """Get synonyms of the index.

        **Returns:** The synonyms of the index.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     synonyms = await index.get_synonyms()
        ```
        """
        url = f"{self._settings_url}/synonyms"
        response = await self._http_requests.get(url)

        if not response.json():
            return None

        return response.json()

    async def update_synonyms(self, body: dict[str, list[str]]) -> TaskId:
        """Update synonyms of the index.

        **Args:**

        * **body:** The synonyms of the index.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_synonyms(
        >>>         {"wolverine": ["xmen", "logan"], "logan": ["wolverine"]}
        >>>     )
        ```
        """
        url = f"{self._settings_url}/synonyms"
        response = await self._http_requests.post(url, body)

        return TaskId(**response.json())

    async def reset_synonyms(self) -> TaskId:
        """Reset synonyms of the index to default values.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.reset_synonyms()
        ```
        """
        url = f"{self._settings_url}/synonyms"
        response = await self._http_requests.delete(url)

        return TaskId(**response.json())

    async def get_filterable_attributes(self) -> list[str] | None:
        """Get filterable attributes of the index.

        **Returns:** List containing the filterable attributes of the index.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     filterable_attributes = await index.get_filterable_attributes()
        ```
        """
        url = f"{self._settings_url}/filterable-attributes"
        response = await self._http_requests.get(url)

        if not response.json():
            return None

        return response.json()

    async def update_filterable_attributes(self, body: list[str]) -> TaskId:
        """Update filterable attributes of the index.

        **Args:**

        * **body:** List containing the filterable attributes of the index.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_filterable_attributes(["genre", "director"])
        ```
        """
        url = f"{self._settings_url}/filterable-attributes"
        response = await self._http_requests.post(url, body)

        return TaskId(**response.json())

    async def reset_filterable_attributes(self) -> TaskId:
        """Reset filterable attributes of the index to default values.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.reset_filterable_attributes()
        ```
        """
        url = f"{self._settings_url}/filterable-attributes"
        response = await self._http_requests.delete(url)

        return TaskId(**response.json())

    async def get_sortable_attributes(self) -> list[str]:
        """Get sortable attributes of the Index.

        **Args:**

        * **sortable_attributes:** List containing the sortable attributes of the index.

        **Returns:** List containing the sortable attributes of the Index.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     sortable_attributes = await index.get_sortable_attributes()
        ```
        """
        url = f"{self._settings_url}/sortable-attributes"
        response = await self._http_requests.get(url)

        return response.json()

    async def update_sortable_attributes(self, sortable_attributes: list[str]) -> TaskId:
        """Get sortable attributes of the Index.

        **Returns:** List containing the sortable attributes of the Index.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.update_sortable_attributes(["title", "release_date"])
        ```
        """
        url = f"{self._settings_url}/sortable-attributes"
        response = await self._http_requests.post(url, sortable_attributes)

        return TaskId(**response.json())

    async def reset_sortable_attributes(self) -> TaskId:
        """Reset sortable attributes of the index to default values.

        **Returns:** Update id to track the action.

        **Raises:**

        * **MeilisearchCommunicationError:** If there was an error communicating with the server.
        * **MeilisearchApiError:** If the MeiliSearch API returned an error.

        Usage:

        ```py
        >>> from meilisearch_async_client import Client
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     await index.reset_sortable_attributes()
        ```
        """
        url = f"{self._settings_url}/sortable-attributes"
        response = await self._http_requests.delete(url)

        return TaskId(**response.json())

    @staticmethod
    async def _batch(documents: list[dict], batch_size: int) -> AsyncGenerator[list[dict], None]:
        total_len = len(documents)
        for i in range(0, total_len, batch_size):
            yield documents[i : i + batch_size]

    @staticmethod
    def _raise_on_no_documents(
        documents: list[Any], document_type: str, directory_path: str | Path
    ) -> None:
        if not documents:
            raise MeiliSearchError(f"No {document_type} files found in {directory_path}")

    @staticmethod
    def _combine_documents(documents: list[list[Any]]) -> list[Any]:
        return [x for y in documents for x in y]

    @staticmethod
    async def _generate_auto_batches(
        documents: list[dict[str, Any]], max_payload_size: int
    ) -> AsyncGenerator[list[dict], None]:
        loop = get_running_loop()

        # Check the size of all documents together if it is below the max size yield it all at onece
        doc_json_str = await loop.run_in_executor(None, partial(json.dumps, documents))
        doc_size = await loop.run_in_executor(None, partial(getsizeof, doc_json_str))
        if doc_size < max_payload_size:
            yield documents
        else:
            batch = []
            batch_size = 0
            for doc in documents:
                doc_json_str = await loop.run_in_executor(None, partial(json.dumps, doc))
                doc_size = await loop.run_in_executor(None, partial(getsizeof, doc_json_str))
                if doc_size > max_payload_size:
                    raise PayloadTooLarge(
                        f"Payload size {doc_size} is greater than the maximum payload size of {max_payload_size}"
                    )
                batch_size += doc_size
                batch.append(doc)
                if batch_size >= max_payload_size:
                    batch.pop()
                    yield batch
                    batch.clear()
                    batch.append(doc)
                    batch_size = doc_size
            if batch:
                yield batch

    @staticmethod
    def _iso_to_date_time(iso_date: datetime | str | None) -> datetime | None:
        """Handle conversion of iso string to datetime.

        The microseconds from MeiliSearch are sometimes too long for python to convert so this
        strips off the last digits to shorten it when that happens.
        """
        if not iso_date:
            return None

        if isinstance(iso_date, datetime):
            return iso_date

        try:
            return datetime.strptime(iso_date, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            split = iso_date.split(".")
            reduce = len(split[1]) - 6
            reduced = f"{split[0]}.{split[1][:-reduce]}Z"
            return datetime.strptime(reduced, "%Y-%m-%dT%H:%M:%S.%fZ")

    @staticmethod
    async def _load_documents_from_file(
        file_path: Path | str,
    ) -> list[dict[Any, Any]]:
        if isinstance(file_path, str):
            file_path = Path(file_path)

        loop = get_running_loop()
        await loop.run_in_executor(None, partial(Index._validate_file_type, file_path))

        if file_path.suffix == ".csv":
            with open(file_path, mode="r") as f:
                documents = await loop.run_in_executor(None, partial(DictReader, f))
                return list(documents)

        if file_path.suffix == ".ndjson":
            with open(file_path, mode="r") as f:
                return [await loop.run_in_executor(None, partial(json.loads, x)) for x in f]

        async with aiofiles.open(file_path, mode="r") as f:  # type: ignore
            data = await f.read()  # type: ignore
            documents = await loop.run_in_executor(None, partial(json.loads, data))

            if not isinstance(documents, list):
                raise InvalidDocumentError("MeiliSearch requires documents to be in a list")

            return documents

    @staticmethod
    def _validate_file_type(file_path: Path) -> None:
        if file_path.suffix not in (".json", ".csv", ".ndjson"):
            raise MeiliSearchError("File must be a json, ndjson, or csv file")
