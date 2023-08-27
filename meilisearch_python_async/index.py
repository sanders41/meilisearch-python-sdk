from __future__ import annotations

import asyncio
import json
from csv import DictReader
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, Generator
from urllib.parse import urlencode

import aiofiles
from httpx import AsyncClient

from meilisearch_python_async._http_requests import HttpRequests
from meilisearch_python_async._utils import is_pydantic_2, iso_to_date_time, use_task_groups
from meilisearch_python_async.errors import InvalidDocumentError, MeilisearchError
from meilisearch_python_async.models.documents import DocumentsInfo
from meilisearch_python_async.models.index import IndexStats
from meilisearch_python_async.models.search import FacetSearchResults, SearchResults
from meilisearch_python_async.models.settings import (
    Faceting,
    MeilisearchSettings,
    Pagination,
    TypoTolerance,
)
from meilisearch_python_async.models.task import TaskInfo
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

        Args:

            http_client: An instance of the AsyncClient. This automatically gets passed by the
                Client when creating and Index instance.
            uid: The index's unique identifier.
            primary_key: The primary key of the documents. Defaults to None.
            created_at: The date and time the index was created. Defaults to None.
            updated_at: The date and time the index was last updated. Defaults to None.
        """
        self.uid = uid
        self.primary_key = primary_key
        self.created_at: datetime | None = iso_to_date_time(created_at)
        self.updated_at: datetime | None = iso_to_date_time(updated_at)
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

    async def delete(self) -> TaskInfo:
        """Deletes the index.

        Returns:

            The details of the task.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.delete()
        """
        url = self._base_url_with_uid
        response = await self._http_requests.delete(url)
        return TaskInfo(**response.json())

    async def delete_if_exists(self) -> bool:
        """Delete the index if it already exists.

        Returns:

            True if the index was deleted or False if not.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.delete_if_exists()
        """
        response = await self.delete()
        status = await wait_for_task(self.http_client, response.task_uid, timeout_in_ms=100000)
        if status.status == "succeeded":
            return True

        return False

    async def update(self, primary_key: str) -> Index:
        """Update the index primary key.

        Args:

            primary_key: The primary key of the documents.

        Returns:

            An instance of the Index with the updated information.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     updated_index = await index.update()
        """
        payload = {"primaryKey": primary_key}
        url = self._base_url_with_uid
        response = await self._http_requests.patch(url, payload)
        await wait_for_task(self.http_client, response.json()["taskUid"], timeout_in_ms=100000)
        index_response = await self._http_requests.get(f"{url}")
        self.primary_key = index_response.json()["primaryKey"]
        return self

    async def fetch_info(self) -> Index:
        """Gets the infromation about the index.

        Returns:

            An instance of the Index containing the retrieved information.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     index_info = await index.fetch_info()
        """
        url = self._base_url_with_uid
        response = await self._http_requests.get(url)
        index_dict = response.json()
        self.primary_key = index_dict["primaryKey"]
        loop = asyncio.get_running_loop()
        self.created_at = await loop.run_in_executor(
            None, partial(iso_to_date_time, index_dict["createdAt"])
        )
        self.updated_at = await loop.run_in_executor(
            None, partial(iso_to_date_time, index_dict["updatedAt"])
        )
        return self

    async def get_primary_key(self) -> str | None:
        """Get the primary key.

        Returns:

            The primary key for the documents in the index.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     primary_key = await index.get_primary_key()
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

        Args:

            http_client: An instance of the AsyncClient. This automatically gets passed by the
                Client when creating and Index instance.
            uid: The index's unique identifier.
            primary_key: The primary key of the documents. Defaults to None.

        Returns:

            An instance of Index containing the information of the newly created index.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = await index.create(client, "movies")
        """
        if not primary_key:
            payload = {"uid": uid}
        else:
            payload = {"primaryKey": primary_key, "uid": uid}

        url = "indexes"
        http_request = HttpRequests(http_client)
        response = await http_request.post(url, payload)
        await wait_for_task(http_client, response.json()["taskUid"], timeout_in_ms=100000)
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

        Returns:

            Stats of the index.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     stats = await index.get_stats()
        """
        url = self._stats_url
        response = await self._http_requests.get(url)

        return IndexStats(**response.json())

    async def search(
        self,
        query: str | None = None,
        *,
        offset: int = 0,
        limit: int = 20,
        filter: str | list[str | list[str]] | None = None,
        facets: list[str] | None = None,
        attributes_to_retrieve: list[str] = ["*"],
        attributes_to_crop: list[str] | None = None,
        crop_length: int = 200,
        attributes_to_highlight: list[str] | None = None,
        sort: list[str] | None = None,
        show_matches_position: bool = False,
        highlight_pre_tag: str = "<em>",
        highlight_post_tag: str = "</em>",
        crop_marker: str = "...",
        matching_strategy: str = "all",
        hits_per_page: int | None = None,
        page: int | None = None,
        attributes_to_search_on: list[str] | None = None,
        show_ranking_score: bool = False,
        show_ranking_score_details: bool = False,
        vector: list[float] | None = None,
    ) -> SearchResults:
        """Search the index.

        Args:

            query: String containing the word(s) to search
            offset: Number of documents to skip. Defaults to 0.
            limit: Maximum number of documents returned. Defaults to 20.
            filter: Filter queries by an attribute value. Defaults to None.
            facets: Facets for which to retrieve the matching count. Defaults to None.
            attributes_to_retrieve: Attributes to display in the returned documents.
                Defaults to ["*"].
            attributes_to_crop: Attributes whose values have to be cropped. Defaults to None.
            crop_length: The maximun number of words to display. Defaults to 200.
            attributes_to_highlight: Attributes whose values will contain highlighted matching terms.
                Defaults to None.
            sort: Attributes by which to sort the results. Defaults to None.
            show_matches_position: Defines whether an object that contains information about the matches should be
                returned or not. Defaults to False.
            highlight_pre_tag: The opening tag for highlighting text. Defaults to <em>.
            highlight_post_tag: The closing tag for highlighting text. Defaults to </em>
            crop_marker: Marker to display when the number of words excedes the `crop_length`.
                Defaults to ...
            matching_strategy: Specifies the matching strategy Meilisearch should use. Defaults to `all`.
            hits_per_page: Sets the number of results returned per page.
            page: Sets the specific results page to fetch.
            attributes_to_search_on: List of field names. Allow search over a subset of searchable
                attributes without modifying the index settings. Defaults to None.
            show_ranking_score: If set to True the ranking score will be returned with each document
                in the search. Defaults to False.
            show_ranking_score_details: If set to True the ranking details will be returned with
                each document in the search. Defaults to False. Note: This parameter can only be
                used with Meilisearch >= v1.3.0, and is experimental in Meilisearch v1.3.0. In order
                to use this feature in Meilisearch v1.3.0 you first need to enable the feature by
                sending a PATCH request to /experimental-features with { "scoreDetails": true }.
                Because this feature is experimental it may be removed or updated causing breaking
                changes in this library without a major version bump so use with caution.
            vector: List of vectors for vector search. Defaults to None. Note: This parameter can
                only be used with Meilisearch >= v1.3.0, and is experimental in Meilisearch v1.3.0.
                In order to use this feature in Meilisearch v1.3.0 you first need to enable the
                feature by sending a PATCH request to /experimental-features with
                { "vectorStore": true }. Because this feature is experimental it may be removed or
                updated causing breaking changes in this library without a major version bump so use
                with caution.

        Returns:

            Results of the search

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     search_results = await index.search("Tron")
        """
        body = _process_search_parameters(
            q=query,
            offset=offset,
            limit=limit,
            filter=filter,
            facets=facets,
            attributes_to_retrieve=attributes_to_retrieve,
            attributes_to_crop=attributes_to_crop,
            crop_length=crop_length,
            attributes_to_highlight=attributes_to_highlight,
            sort=sort,
            show_matches_position=show_matches_position,
            highlight_pre_tag=highlight_pre_tag,
            highlight_post_tag=highlight_post_tag,
            crop_marker=crop_marker,
            matching_strategy=matching_strategy,
            hits_per_page=hits_per_page,
            page=page,
            attributes_to_search_on=attributes_to_search_on,
            show_ranking_score=show_ranking_score,
            show_ranking_score_details=show_ranking_score_details,
            vector=vector,
        )

        url = f"{self._base_url_with_uid}/search"
        response = await self._http_requests.post(url, body=body)

        return SearchResults(**response.json())

    async def facet_search(
        self,
        query: str | None = None,
        *,
        facet_name: str,
        facet_query: str,
        offset: int = 0,
        limit: int = 20,
        filter: str | list[str | list[str]] | None = None,
        facets: list[str] | None = None,
        attributes_to_retrieve: list[str] = ["*"],
        attributes_to_crop: list[str] | None = None,
        crop_length: int = 200,
        attributes_to_highlight: list[str] | None = None,
        sort: list[str] | None = None,
        show_matches_position: bool = False,
        highlight_pre_tag: str = "<em>",
        highlight_post_tag: str = "</em>",
        crop_marker: str = "...",
        matching_strategy: str = "all",
        hits_per_page: int | None = None,
        page: int | None = None,
        attributes_to_search_on: list[str] | None = None,
        show_ranking_score: bool = False,
        show_ranking_score_details: bool = False,
        vector: list[float] | None = None,
    ) -> FacetSearchResults:
        """Search the index.

        Args:

            query: String containing the word(s) to search
            facet_name: The name of the facet to search
            facet_query: The facet search value
            offset: Number of documents to skip. Defaults to 0.
            limit: Maximum number of documents returned. Defaults to 20.
            filter: Filter queries by an attribute value. Defaults to None.
            facets: Facets for which to retrieve the matching count. Defaults to None.
            attributes_to_retrieve: Attributes to display in the returned documents.
                Defaults to ["*"].
            attributes_to_crop: Attributes whose values have to be cropped. Defaults to None.
            crop_length: The maximun number of words to display. Defaults to 200.
            attributes_to_highlight: Attributes whose values will contain highlighted matching terms.
                Defaults to None.
            sort: Attributes by which to sort the results. Defaults to None.
            show_matches_position: Defines whether an object that contains information about the matches should be
                returned or not. Defaults to False.
            highlight_pre_tag: The opening tag for highlighting text. Defaults to <em>.
            highlight_post_tag: The closing tag for highlighting text. Defaults to </em>
            crop_marker: Marker to display when the number of words excedes the `crop_length`.
                Defaults to ...
            matching_strategy: Specifies the matching strategy Meilisearch should use. Defaults to `all`.
            hits_per_page: Sets the number of results returned per page.
            page: Sets the specific results page to fetch.
            attributes_to_search_on: List of field names. Allow search over a subset of searchable
                attributes without modifying the index settings. Defaults to None.
            show_ranking_score: If set to True the ranking score will be returned with each document
                in the search. Defaults to False.
            show_ranking_score_details: If set to True the ranking details will be returned with
                each document in the search. Defaults to False. Note: This parameter can only be
                used with Meilisearch >= v1.3.0, and is experimental in Meilisearch v1.3.0. In order
                to use this feature in Meilisearch v1.3.0 you first need to enable the feature by
                sending a PATCH request to /experimental-features with { "scoreDetails": true }.
                Because this feature is experimental it may be removed or updated causing breaking
                changes in this library without a major version bump so use with caution.
            vector: List of vectors for vector search. Defaults to None. Note: This parameter can
                only be used with Meilisearch >= v1.3.0, and is experimental in Meilisearch v1.3.0.
                In order to use this feature in Meilisearch v1.3.0 you first need to enable the
                feature by sending a PATCH request to /experimental-features with
                { "vectorStore": true }. Because this feature is experimental it may be removed or
                updated causing breaking changes in this library without a major version bump so use
                with caution.

        Returns:

            Results of the search

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     search_results = await index.search(
            >>>         "Tron",
            >>>         facet_name="genre",
            >>>         facet_query="Sci-fi"
            >>>     )
        """
        body = _process_search_parameters(
            q=query,
            facet_name=facet_name,
            facet_query=facet_query,
            offset=offset,
            limit=limit,
            filter=filter,
            facets=facets,
            attributes_to_retrieve=attributes_to_retrieve,
            attributes_to_crop=attributes_to_crop,
            crop_length=crop_length,
            attributes_to_highlight=attributes_to_highlight,
            sort=sort,
            show_matches_position=show_matches_position,
            highlight_pre_tag=highlight_pre_tag,
            highlight_post_tag=highlight_post_tag,
            crop_marker=crop_marker,
            matching_strategy=matching_strategy,
            hits_per_page=hits_per_page,
            page=page,
            attributes_to_search_on=attributes_to_search_on,
            show_ranking_score=show_ranking_score,
            show_ranking_score_details=show_ranking_score_details,
            vector=vector,
        )

        url = f"{self._base_url_with_uid}/facet-search"
        response = await self._http_requests.post(url, body=body)

        return FacetSearchResults(**response.json())

    async def get_document(self, document_id: str) -> dict[str, Any]:
        """Get one document with given document identifier.

        Args:

            document_id: Unique identifier of the document.

        Returns:

            The document information

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     document = await index.get_document("1234")
        """
        url = f"{self._documents_url}/{document_id}"
        response = await self._http_requests.get(url)

        return response.json()

    async def get_documents(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        fields: list[str] | None = None,
        filter: str | list[str | list[str]] | None = None,
    ) -> DocumentsInfo:
        """Get a batch documents from the index.

        Args:

            offset: Number of documents to skip. Defaults to 0.
            limit: Maximum number of documents returnedd. Defaults to 20.
            fields: Document attributes to show. If this value is None then all
                attributes are retrieved. Defaults to None.
            filter: Filter value information. Defaults to None. Note: This parameter can only be
                used with Meilisearch >= v1.2.0

        Returns:

            Documents info.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.


        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     documents = await index.get_documents()
        """
        parameters: dict[str, Any] = {
            "offset": offset,
            "limit": limit,
        }

        if not filter:
            if fields:
                parameters["fields"] = ",".join(fields)

            url = f"{self._documents_url}?{urlencode(parameters)}"
            response = await self._http_requests.get(url)

            return DocumentsInfo(**response.json())

        if fields:
            parameters["fields"] = fields

        parameters["filter"] = filter

        url = f"{self._documents_url}/fetch"
        response = await self._http_requests.post(url, body=parameters)

        return DocumentsInfo(**response.json())

    async def add_documents(
        self, documents: list[dict[str, Any]], primary_key: str | None = None
    ) -> TaskInfo:
        """Add documents to the index.

        Args:

            documents: List of documents.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.

        Returns:

            The details of the task.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> documents = [
            >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
            >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
            >>> ]
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.add_documents(documents)
        """
        url = self._documents_url
        if primary_key:
            formatted_primary_key = urlencode({"primaryKey": primary_key})
            url = f"{url}?{formatted_primary_key}"

        response = await self._http_requests.post(url, documents)

        return TaskInfo(**response.json())

    async def add_documents_in_batches(
        self,
        documents: list[dict[str, Any]],
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
    ) -> list[TaskInfo]:
        """Adds documents in batches to reduce RAM usage with indexing.

        Args:

            documents: List of documents.
            batch_size: The number of documents that should be included in each batch.
                Defaults to 1000.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.

        Returns:

            List of update ids to track the action.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> >>> documents = [
            >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
            >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
            >>> ]
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.add_documents_in_batches(documents)
        """
        if not use_task_groups():
            batches = [self.add_documents(x, primary_key) for x in _batch(documents, batch_size)]
            return await asyncio.gather(*batches)

        async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
            tasks = [
                tg.create_task(self.add_documents(x, primary_key))
                for x in _batch(documents, batch_size)
            ]

        return [x.result() for x in tasks]

    async def add_documents_from_directory(
        self,
        directory_path: Path | str,
        *,
        primary_key: str | None = None,
        document_type: str = "json",
        csv_delimiter: str | None = None,
        combine_documents: bool = True,
    ) -> list[TaskInfo]:
        """Load all json files from a directory and add the documents to the index.

        Args:

            directory_path: Path to the directory that contains the json files.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            document_type: The type of document being added. Accepted types are json, csv, and
                ndjson. For csv files the first row of the document should be a header row contining
                the field names, and ever for should have a title.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            combine_documents: If set to True this will combine the documents from all the files
                before indexing them. Defaults to True.

        Returns:

            The details of the task status.

        Raises:

            InvalidDocumentError: If the docucment is not a valid format for Meilisearch.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from pathlib import Path
            >>> from meilisearch_python_async import Client
            >>> directory_path = Path("/path/to/directory/containing/files")
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.add_documents_from_directory(directory_path)
        """
        directory = Path(directory_path) if isinstance(directory_path, str) else directory_path

        if combine_documents:
            all_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await _load_documents_from_file(path, csv_delimiter)
                    all_documents.append(documents)

            _raise_on_no_documents(all_documents, document_type, directory_path)

            loop = asyncio.get_running_loop()
            combined = await loop.run_in_executor(None, partial(_combine_documents, all_documents))

            response = await self.add_documents(combined, primary_key)

            return [response]

        if not use_task_groups():
            add_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await _load_documents_from_file(path, csv_delimiter)
                    add_documents.append(self.add_documents(documents, primary_key))

            _raise_on_no_documents(add_documents, document_type, directory_path)

            if len(add_documents) > 1:
                # Send the first document on its own before starting the gather. Otherwise Meilisearch
                # returns an error because it thinks all entries are trying to create the same index.
                first_response = [await add_documents.pop()]

                responses = await asyncio.gather(*add_documents)
                responses = [*first_response, *responses]
            else:
                responses = [await add_documents[0]]

            return responses

        async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
            tasks = []
            all_results = []
            for i, path in enumerate(directory.iterdir()):
                if path.suffix == f".{document_type}":
                    documents = await _load_documents_from_file(path, csv_delimiter)
                    if i == 0:
                        all_results = [await self.add_documents(documents)]
                    else:
                        tasks.append(tg.create_task(self.add_documents(documents, primary_key)))

        results = [x.result() for x in tasks]
        all_results = [*all_results, *results]
        _raise_on_no_documents(all_results, document_type, directory_path)
        return all_results

    async def add_documents_from_directory_in_batches(
        self,
        directory_path: Path | str,
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
        document_type: str = "json",
        csv_delimiter: str | None = None,
        combine_documents: bool = True,
    ) -> list[TaskInfo]:
        """Load all json files from a directory and add the documents to the index in batches.

        Args:

            directory_path: Path to the directory that contains the json files.
            batch_size: The number of documents that should be included in each batch.
                Defaults to 1000.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            document_type: The type of document being added. Accepted types are json, csv, and
                ndjson. For csv files the first row of the document should be a header row contining
                the field names, and ever for should have a title.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            combine_documents: If set to True this will combine the documents from all the files
                before indexing them. Defaults to True.

        Returns:

            List of update ids to track the action.

        Raises:

            InvalidDocumentError: If the docucment is not a valid format for Meilisearch.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from pathlib import Path
            >>> from meilisearch_python_async import Client
            >>> directory_path = Path("/path/to/directory/containing/files")
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.add_documents_from_directory_in_batches(directory_path)
        """
        directory = Path(directory_path) if isinstance(directory_path, str) else directory_path

        if combine_documents:
            all_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await _load_documents_from_file(path, csv_delimiter=csv_delimiter)
                    all_documents.append(documents)

            _raise_on_no_documents(all_documents, document_type, directory_path)

            loop = asyncio.get_running_loop()
            combined = await loop.run_in_executor(None, partial(_combine_documents, all_documents))

            return await self.add_documents_in_batches(
                combined, batch_size=batch_size, primary_key=primary_key
            )

        responses: list[TaskInfo] = []

        add_documents = []
        for path in directory.iterdir():
            if path.suffix == f".{document_type}":
                documents = await _load_documents_from_file(path, csv_delimiter)
                add_documents.append(
                    self.add_documents_in_batches(
                        documents, batch_size=batch_size, primary_key=primary_key
                    )
                )

        _raise_on_no_documents(add_documents, document_type, directory_path)

        if len(add_documents) > 1:
            # Send the first document on its own before starting the gather. Otherwise Meilisearch
            # returns an error because it thinks all entries are trying to create the same index.
            first_response = await add_documents.pop()
            responses_gather = await asyncio.gather(*add_documents)
            responses = [*first_response, *[x for y in responses_gather for x in y]]
        else:
            responses = await add_documents[0]

        return responses

    async def add_documents_from_file(
        self, file_path: Path | str, primary_key: str | None = None
    ) -> TaskInfo:
        """Add documents to the index from a json file.

        Args:

            file_path: Path to the json file.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.

        Returns:

            The details of the task status.

        Raises:

            InvalidDocumentError: If the docucment is not a valid format for Meilisearch.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from pathlib import Path
            >>> from meilisearch_python_async import Client
            >>> file_path = Path("/path/to/file.json")
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.add_documents_from_file(file_path)
        """
        documents = await _load_documents_from_file(file_path)

        return await self.add_documents(documents, primary_key=primary_key)

    async def add_documents_from_file_in_batches(
        self,
        file_path: Path | str,
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
        csv_delimiter: str | None = None,
    ) -> list[TaskInfo]:
        """Adds documents form a json file in batches to reduce RAM usage with indexing.

        Args:

            file_path: Path to the json file.
            batch_size: The number of documents that should be included in each batch.
                Defaults to 1000.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.

        Returns:

            List of update ids to track the action.

        Raises:

            InvalidDocumentError: If the docucment is not a valid format for Meilisearch.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from pathlib import Path
            >>> from meilisearch_python_async import Client
            >>> file_path = Path("/path/to/file.json")
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.add_documents_from_file_in_batches(file_path)
        """
        documents = await _load_documents_from_file(file_path, csv_delimiter)

        return await self.add_documents_in_batches(
            documents, batch_size=batch_size, primary_key=primary_key
        )

    async def add_documents_from_raw_file(
        self,
        file_path: Path | str,
        primary_key: str | None = None,
        *,
        csv_delimiter: str | None = None,
    ) -> TaskInfo:
        """Directly send csv or ndjson files to Meilisearch without pre-processing.

        The can reduce RAM usage from Meilisearch during indexing, but does not include the option
        for batching.

        Args:

            file_path: The path to the file to send to Meilisearch. Only csv and ndjson files are
                allowed.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.

        Returns:

            The details of the task.

        Raises:

            ValueError: If the file is not a csv or ndjson file, or if a csv_delimiter is sent for
                a non-csv file.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from pathlib import Path
            >>> from meilisearch_python_async import Client
            >>> file_path = Path("/path/to/file.csv")
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.add_documents_from_raw_file(file_path)
        """
        upload_path = Path(file_path) if isinstance(file_path, str) else file_path
        if not upload_path.exists():
            raise MeilisearchError("No file found at the specified path")

        if upload_path.suffix not in (".csv", ".ndjson"):
            raise ValueError("Only csv and ndjson files can be sent as binary files")

        if csv_delimiter and upload_path.suffix != ".csv":
            raise ValueError("A csv_delimiter can only be used with csv files")

        if (
            csv_delimiter
            and len(csv_delimiter) != 1
            or csv_delimiter
            and not csv_delimiter.isascii()
        ):
            raise ValueError("csv_delimiter must be a single ascii character")

        content_type = "text/csv" if upload_path.suffix == ".csv" else "application/x-ndjson"
        url = self._documents_url
        parameters = {}

        if primary_key:
            parameters["primaryKey"] = primary_key
        if csv_delimiter:
            parameters["csvDelimiter"] = csv_delimiter

        if parameters:
            url = f"{url}?{urlencode(parameters)}"

        async with aiofiles.open(upload_path, "r") as f:
            data = await f.read()

        response = await self._http_requests.post(url, body=data, content_type=content_type)

        return TaskInfo(**response.json())

    async def update_documents(
        self, documents: list[dict[str, Any]], primary_key: str | None = None
    ) -> TaskInfo:
        """Update documents in the index.

        Args:

            documents: List of documents.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.

        Returns:

            The details of the task.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> documents = [
            >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
            >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
            >>> ]
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_documents(documents)
        """
        url = self._documents_url
        if primary_key:
            formatted_primary_key = urlencode({"primaryKey": primary_key})
            url = f"{url}?{formatted_primary_key}"

        response = await self._http_requests.put(url, documents)

        return TaskInfo(**response.json())

    async def update_documents_in_batches(
        self,
        documents: list[dict[str, Any]],
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
    ) -> list[TaskInfo]:
        """Update documents in batches to reduce RAM usage with indexing.

        Each batch tries to fill the max_payload_size

        Args:

            documents: List of documents.
            batch_size: The number of documents that should be included in each batch.
                Defaults to 1000.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.

        Returns:

            List of update ids to track the action.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> documents = [
            >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
            >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
            >>> ]
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_documents_in_batches(documents)
        """
        if not use_task_groups():
            batches = [self.update_documents(x, primary_key) for x in _batch(documents, batch_size)]
            return await asyncio.gather(*batches)

        async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
            tasks = [
                tg.create_task(self.update_documents(x, primary_key))
                for x in _batch(documents, batch_size)
            ]
        return [x.result() for x in tasks]

    async def update_documents_from_directory(
        self,
        directory_path: Path | str,
        *,
        primary_key: str | None = None,
        document_type: str = "json",
        csv_delimiter: str | None = None,
        combine_documents: bool = True,
    ) -> list[TaskInfo]:
        """Load all json files from a directory and update the documents.

        Args:

            directory_path: Path to the directory that contains the json files.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            document_type: The type of document being added. Accepted types are json, csv, and
                ndjson. For csv files the first row of the document should be a header row contining
                the field names, and ever for should have a title.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            combine_documents: If set to True this will combine the documents from all the files
                before indexing them. Defaults to True.

        Returns:

            The details of the task status.

        Raises:

            InvalidDocumentError: If the docucment is not a valid format for Meilisearch.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from pathlib import Path
            >>> from meilisearch_python_async import Client
            >>> directory_path = Path("/path/to/directory/containing/files")
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_documents_from_directory(directory_path)
        """
        directory = Path(directory_path) if isinstance(directory_path, str) else directory_path

        if combine_documents:
            all_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await _load_documents_from_file(path, csv_delimiter)
                    all_documents.append(documents)

            _raise_on_no_documents(all_documents, document_type, directory_path)

            loop = asyncio.get_running_loop()
            combined = await loop.run_in_executor(None, partial(_combine_documents, all_documents))

            response = await self.update_documents(combined, primary_key)
            return [response]

        if not use_task_groups():
            update_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await _load_documents_from_file(path, csv_delimiter)
                    update_documents.append(self.update_documents(documents, primary_key))

            _raise_on_no_documents(update_documents, document_type, directory_path)

            if len(update_documents) > 1:
                # Send the first document on its own before starting the gather. Otherwise Meilisearch
                # returns an error because it thinks all entries are trying to create the same index.
                first_response = [await update_documents.pop()]
                responses = await asyncio.gather(*update_documents)
                responses = [*first_response, *responses]
            else:
                responses = [await update_documents[0]]

            return responses

        async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
            tasks = []
            results = []
            for i, path in enumerate(directory.iterdir()):
                if path.suffix == f".{document_type}":
                    documents = await _load_documents_from_file(path, csv_delimiter)
                    if i == 0:
                        results = [await self.update_documents(documents, primary_key)]
                    else:
                        tasks.append(tg.create_task(self.update_documents(documents, primary_key)))

        results = [*results, *[x.result() for x in tasks]]
        _raise_on_no_documents(results, document_type, directory_path)
        return results

    async def update_documents_from_directory_in_batches(
        self,
        directory_path: Path | str,
        *,
        batch_size: int = 1000,
        primary_key: str | None = None,
        document_type: str = "json",
        csv_delimiter: str | None = None,
        combine_documents: bool = True,
    ) -> list[TaskInfo]:
        """Load all json files from a directory and update the documents.

        Args:

            directory_path: Path to the directory that contains the json files.
            batch_size: The number of documents that should be included in each batch.
                Defaults to 1000.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            document_type: The type of document being added. Accepted types are json, csv, and
                ndjson. For csv files the first row of the document should be a header row contining
                the field names, and ever for should have a title.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.
            combine_documents: If set to True this will combine the documents from all the files
                before indexing them. Defaults to True.

        Returns:

            List of update ids to track the action.

        Raises:

            InvalidDocumentError: If the docucment is not a valid format for Meilisearch.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from pathlib import Path
            >>> from meilisearch_python_async import Client
            >>> directory_path = Path("/path/to/directory/containing/files")
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_documents_from_directory_in_batches(directory_path)
        """
        directory = Path(directory_path) if isinstance(directory_path, str) else directory_path

        if combine_documents:
            all_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await _load_documents_from_file(path, csv_delimiter)
                    all_documents.append(documents)

            _raise_on_no_documents(all_documents, document_type, directory_path)

            loop = asyncio.get_running_loop()
            combined = await loop.run_in_executor(None, partial(_combine_documents, all_documents))

            return await self.update_documents_in_batches(
                combined, batch_size=batch_size, primary_key=primary_key
            )

        if not use_task_groups():
            responses: list[TaskInfo] = []

            update_documents = []
            for path in directory.iterdir():
                if path.suffix == f".{document_type}":
                    documents = await _load_documents_from_file(path, csv_delimiter)
                    update_documents.append(
                        self.update_documents_in_batches(
                            documents, batch_size=batch_size, primary_key=primary_key
                        )
                    )

            _raise_on_no_documents(update_documents, document_type, directory_path)

            if len(update_documents) > 1:
                # Send the first document on its own before starting the gather. Otherwise Meilisearch
                # returns an error because it thinks all entries are trying to create the same index.
                first_response = await update_documents.pop()
                responses_gather = await asyncio.gather(*update_documents)
                responses = [*first_response, *[x for y in responses_gather for x in y]]
            else:
                responses = await update_documents[0]

            return responses

        async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
            results = []
            tasks = []
            for i, path in enumerate(directory.iterdir()):
                if path.suffix == f".{document_type}":
                    documents = await _load_documents_from_file(path, csv_delimiter)
                    if i == 0:
                        results = await self.update_documents_in_batches(
                            documents, batch_size=batch_size, primary_key=primary_key
                        )
                    else:
                        tasks.append(
                            tg.create_task(
                                self.update_documents_in_batches(
                                    documents, batch_size=batch_size, primary_key=primary_key
                                )
                            )
                        )

        results = [*results, *[x for y in tasks for x in y.result()]]
        _raise_on_no_documents(results, document_type, directory_path)
        return results

    async def update_documents_from_file(
        self,
        file_path: Path | str,
        primary_key: str | None = None,
        csv_delimiter: str | None = None,
    ) -> TaskInfo:
        """Add documents in the index from a json file.

        Args:

            file_path: Path to the json file.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from pathlib import Path
            >>> from meilisearch_python_async import Client
            >>> file_path = Path("/path/to/file.json")
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_documents_from_file(file_path)
        """
        documents = await _load_documents_from_file(file_path, csv_delimiter)

        return await self.update_documents(documents, primary_key=primary_key)

    async def update_documents_from_file_in_batches(
        self, file_path: Path | str, *, batch_size: int = 1000, primary_key: str | None = None
    ) -> list[TaskInfo]:
        """Updates documents form a json file in batches to reduce RAM usage with indexing.

        Args:

            file_path: Path to the json file.
            batch_size: The number of documents that should be included in each batch.
                Defaults to 1000.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.

        Returns:

            List of update ids to track the action.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from pathlib import Path
            >>> from meilisearch_python_async import Client
            >>> file_path = Path("/path/to/file.json")
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_documents_from_file_in_batches(file_path)
        """
        documents = await _load_documents_from_file(file_path)

        return await self.update_documents_in_batches(
            documents, batch_size=batch_size, primary_key=primary_key
        )

    async def update_documents_from_raw_file(
        self,
        file_path: Path | str,
        primary_key: str | None = None,
        csv_delimiter: str | None = None,
    ) -> TaskInfo:
        """Directly send csv or ndjson files to Meilisearch without pre-processing.

        The can reduce RAM usage from Meilisearch during indexing, but does not include the option
        for batching.

        Args:

            file_path: The path to the file to send to Meilisearch. Only csv and ndjson files are
                allowed.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.
            csv_delimiter: A single ASCII character to specify the delimiter for csv files. This
                can only be used if the file is a csv file. Defaults to comma.

        Returns:

            The details of the task status.

        Raises:

            ValueError: If the file is not a csv or ndjson file, or if a csv_delimiter is sent for
                a non-csv file.
            MeilisearchError: If the file path is not valid
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from pathlib import Path
            >>> from meilisearch_python_async import Client
            >>> file_path = Path("/path/to/file.csv")
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_documents_from_raw_file(file_path)
        """
        upload_path = Path(file_path) if isinstance(file_path, str) else file_path
        if not upload_path.exists():
            raise MeilisearchError("No file found at the specified path")

        if upload_path.suffix not in (".csv", ".ndjson"):
            raise ValueError("Only csv and ndjson files can be sent as binary files")

        if csv_delimiter and upload_path.suffix != ".csv":
            raise ValueError("A csv_delimiter can only be used with csv files")

        if (
            csv_delimiter
            and len(csv_delimiter) != 1
            or csv_delimiter
            and not csv_delimiter.isascii()
        ):
            raise ValueError("csv_delimiter must be a single ascii character")

        content_type = "text/csv" if upload_path.suffix == ".csv" else "application/x-ndjson"
        url = self._documents_url
        parameters = {}

        if primary_key:
            parameters["primaryKey"] = primary_key
        if csv_delimiter:
            parameters["csvDelimiter"] = csv_delimiter

        if parameters:
            url = f"{url}?{urlencode(parameters)}"

        async with aiofiles.open(upload_path, "r") as f:
            data = await f.read()

        response = await self._http_requests.put(url, body=data, content_type=content_type)

        return TaskInfo(**response.json())

    async def delete_document(self, document_id: str) -> TaskInfo:
        """Delete one document from the index.

        Args:

            document_id: Unique identifier of the document.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.delete_document("1234")
        """
        url = f"{self._documents_url}/{document_id}"
        response = await self._http_requests.delete(url)

        return TaskInfo(**response.json())

    async def delete_documents(self, ids: list[str]) -> TaskInfo:
        """Delete multiple documents from the index.

        Args:

            ids: List of unique identifiers of documents.

        Returns:

            List of update ids to track the action.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.delete_documents(["1234", "5678"])
        """
        url = f"{self._documents_url}/delete-batch"
        response = await self._http_requests.post(url, ids)

        return TaskInfo(**response.json())

    async def delete_documents_by_filter(self, filter: str | list[str | list[str]]) -> TaskInfo:
        """Delete documents from the index by filter.

        Args:

            filter: The filter value information.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.delete_documents_by_filter("genre=horor"))
        """
        url = f"{self._documents_url}/delete"
        response = await self._http_requests.post(url, body={"filter": filter})

        return TaskInfo(**response.json())

    async def delete_documents_in_batches_by_filter(
        self, filters: list[str | list[str | list[str]]]
    ) -> list[TaskInfo]:
        """Delete batches of documents from the index by filter.

        Args:

            filters: A list of filter value information.

        Returns:

            The a list of details of the task statuses.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.delete_documents_in_batches_by_filter(
            >>>         [
            >>>             "genre=horor"),
            >>>             "release_date=1520035200"),
            >>>         ]
            >>>     )
        """
        if not use_task_groups():
            tasks = [self.delete_documents_by_filter(filter) for filter in filters]
            return await asyncio.gather(*tasks)

        async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
            tg_tasks = [
                tg.create_task(self.delete_documents_by_filter(filter)) for filter in filters
            ]

        return [x.result() for x in tg_tasks]

    async def delete_all_documents(self) -> TaskInfo:
        """Delete all documents from the index.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.delete_all_document()
        """
        url = self._documents_url
        response = await self._http_requests.delete(url)

        return TaskInfo(**response.json())

    async def get_settings(self) -> MeilisearchSettings:
        """Get settings of the index.

        Returns:

            Settings of the index.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     settings = await index.get_settings()
        """
        url = self._settings_url
        response = await self._http_requests.get(url)

        return MeilisearchSettings(**response.json())

    async def update_settings(self, body: MeilisearchSettings) -> TaskInfo:
        """Update settings of the index.

        Args:

            body: Settings of the index.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> from meilisearch_python_async import MeilisearchSettings
            >>> new_settings = MeilisearchSettings(
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
        """
        if is_pydantic_2():
            body_dict = {k: v for k, v in body.model_dump(by_alias=True).items() if v is not None}  # type: ignore[attr-defined]
        else:  # pragma: no cover
            body_dict = {k: v for k, v in body.dict(by_alias=True).items() if v is not None}  # type: ignore[attr-defined]

        url = self._settings_url
        response = await self._http_requests.patch(url, body_dict)

        return TaskInfo(**response.json())

    async def reset_settings(self) -> TaskInfo:
        """Reset settings of the index to default values.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_settings()
        """
        url = self._settings_url
        response = await self._http_requests.delete(url)

        return TaskInfo(**response.json())

    async def get_ranking_rules(self) -> list[str]:
        """Get ranking rules of the index.

        Returns:

            List containing the ranking rules of the index.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     ranking_rules = await index.get_ranking_rules()
        """
        url = f"{self._settings_url}/ranking-rules"
        response = await self._http_requests.get(url)

        return response.json()

    async def update_ranking_rules(self, ranking_rules: list[str]) -> TaskInfo:
        """Update ranking rules of the index.

        Args:

            ranking_rules: List containing the ranking rules.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
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
        """
        url = f"{self._settings_url}/ranking-rules"
        response = await self._http_requests.put(url, ranking_rules)

        return TaskInfo(**response.json())

    async def reset_ranking_rules(self) -> TaskInfo:
        """Reset ranking rules of the index to default values.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_ranking_rules()
        """
        url = f"{self._settings_url}/ranking-rules"
        response = await self._http_requests.delete(url)

        return TaskInfo(**response.json())

    async def get_distinct_attribute(self) -> str | None:
        """Get distinct attribute of the index.

        Returns:

            String containing the distinct attribute of the index. If no distinct attribute
                `None` is returned.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     distinct_attribute = await index.get_distinct_attribute()
        """
        url = f"{self._settings_url}/distinct-attribute"
        response = await self._http_requests.get(url)

        if not response.json():
            None

        return response.json()

    async def update_distinct_attribute(self, body: str) -> TaskInfo:
        """Update distinct attribute of the index.

        Args:

            body: Distinct attribute.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_distinct_attribute("url")
        """
        url = f"{self._settings_url}/distinct-attribute"
        response = await self._http_requests.put(url, body)

        return TaskInfo(**response.json())

    async def reset_distinct_attribute(self) -> TaskInfo:
        """Reset distinct attribute of the index to default values.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_distinct_attributes()
        """
        url = f"{self._settings_url}/distinct-attribute"
        response = await self._http_requests.delete(url)

        return TaskInfo(**response.json())

    async def get_searchable_attributes(self) -> list[str]:
        """Get searchable attributes of the index.

        Returns:

            List containing the searchable attributes of the index.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     searchable_attributes = await index.get_searchable_attributes()
        """
        url = f"{self._settings_url}/searchable-attributes"
        response = await self._http_requests.get(url)

        return response.json()

    async def update_searchable_attributes(self, body: list[str]) -> TaskInfo:
        """Update searchable attributes of the index.

        Args:

            body: List containing the searchable attributes.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_searchable_attributes(["title", "description", "genre"])
        """
        url = f"{self._settings_url}/searchable-attributes"
        response = await self._http_requests.put(url, body)

        return TaskInfo(**response.json())

    async def reset_searchable_attributes(self) -> TaskInfo:
        """Reset searchable attributes of the index to default values.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_searchable_attributes()
        """
        url = f"{self._settings_url}/searchable-attributes"
        response = await self._http_requests.delete(url)

        return TaskInfo(**response.json())

    async def get_displayed_attributes(self) -> list[str]:
        """Get displayed attributes of the index.

        Returns:

            List containing the displayed attributes of the index.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     displayed_attributes = await index.get_displayed_attributes()
        """
        url = f"{self._settings_url}/displayed-attributes"
        response = await self._http_requests.get(url)

        return response.json()

    async def update_displayed_attributes(self, body: list[str]) -> TaskInfo:
        """Update displayed attributes of the index.

        Args:

            body: List containing the displayed attributes.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_displayed_attributes(
            >>>         ["title", "description", "genre", "release_date"]
            >>>     )
        """
        url = f"{self._settings_url}/displayed-attributes"
        response = await self._http_requests.put(url, body)

        return TaskInfo(**response.json())

    async def reset_displayed_attributes(self) -> TaskInfo:
        """Reset displayed attributes of the index to default values.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_displayed_attributes()
        """
        url = f"{self._settings_url}/displayed-attributes"
        response = await self._http_requests.delete(url)

        return TaskInfo(**response.json())

    async def get_stop_words(self) -> list[str] | None:
        """Get stop words of the index.

        Returns:

            List containing the stop words of the index.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     stop_words = await index.get_stop_words()
        """
        url = f"{self._settings_url}/stop-words"
        response = await self._http_requests.get(url)

        if not response.json():
            return None

        return response.json()

    async def update_stop_words(self, body: list[str]) -> TaskInfo:
        """Update stop words of the index.

        Args:

            body: List containing the stop words of the index.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_stop_words(["the", "a", "an"])
        """
        url = f"{self._settings_url}/stop-words"
        response = await self._http_requests.put(url, body)

        return TaskInfo(**response.json())

    async def reset_stop_words(self) -> TaskInfo:
        """Reset stop words of the index to default values.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_stop_words()
        """
        url = f"{self._settings_url}/stop-words"
        response = await self._http_requests.delete(url)

        return TaskInfo(**response.json())

    async def get_synonyms(self) -> dict[str, list[str]] | None:
        """Get synonyms of the index.

        Returns:

            The synonyms of the index.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     synonyms = await index.get_synonyms()
        """
        url = f"{self._settings_url}/synonyms"
        response = await self._http_requests.get(url)

        if not response.json():
            return None

        return response.json()

    async def update_synonyms(self, body: dict[str, list[str]]) -> TaskInfo:
        """Update synonyms of the index.

        Args:

            body: The synonyms of the index.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_synonyms(
            >>>         {"wolverine": ["xmen", "logan"], "logan": ["wolverine"]}
            >>>     )
        """
        url = f"{self._settings_url}/synonyms"
        response = await self._http_requests.put(url, body)

        return TaskInfo(**response.json())

    async def reset_synonyms(self) -> TaskInfo:
        """Reset synonyms of the index to default values.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_synonyms()
        """
        url = f"{self._settings_url}/synonyms"
        response = await self._http_requests.delete(url)

        return TaskInfo(**response.json())

    async def get_filterable_attributes(self) -> list[str] | None:
        """Get filterable attributes of the index.

        Returns:

            List containing the filterable attributes of the index.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     filterable_attributes = await index.get_filterable_attributes()
        """
        url = f"{self._settings_url}/filterable-attributes"
        response = await self._http_requests.get(url)

        if not response.json():
            return None

        return response.json()

    async def update_filterable_attributes(self, body: list[str]) -> TaskInfo:
        """Update filterable attributes of the index.

        Args:

            body: List containing the filterable attributes of the index.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_filterable_attributes(["genre", "director"])
        """
        url = f"{self._settings_url}/filterable-attributes"
        response = await self._http_requests.put(url, body)

        return TaskInfo(**response.json())

    async def reset_filterable_attributes(self) -> TaskInfo:
        """Reset filterable attributes of the index to default values.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_filterable_attributes()
        """
        url = f"{self._settings_url}/filterable-attributes"
        response = await self._http_requests.delete(url)

        return TaskInfo(**response.json())

    async def get_sortable_attributes(self) -> list[str]:
        """Get sortable attributes of the Index.

        Returns:

            List containing the sortable attributes of the Index.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     sortable_attributes = await index.get_sortable_attributes()
        """
        url = f"{self._settings_url}/sortable-attributes"
        response = await self._http_requests.get(url)

        return response.json()

    async def update_sortable_attributes(self, sortable_attributes: list[str]) -> TaskInfo:
        """Get sortable attributes of the Index.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_sortable_attributes(["title", "release_date"])
        """
        url = f"{self._settings_url}/sortable-attributes"
        response = await self._http_requests.put(url, sortable_attributes)

        return TaskInfo(**response.json())

    async def reset_sortable_attributes(self) -> TaskInfo:
        """Reset sortable attributes of the index to default values.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_sortable_attributes()
        """
        url = f"{self._settings_url}/sortable-attributes"
        response = await self._http_requests.delete(url)

        return TaskInfo(**response.json())

    async def get_typo_tolerance(self) -> TypoTolerance:
        """Get typo tolerance for the index.

        Returns:

            TypoTolerance for the index.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     sortable_attributes = await index.get_typo_tolerance()
        """
        url = f"{self._settings_url}/typo-tolerance"
        response = await self._http_requests.get(url)

        return TypoTolerance(**response.json())

    async def update_typo_tolerance(self, typo_tolerance: TypoTolerance) -> TaskInfo:
        """Update typo tolerance.

        Returns:

            Task to track the action.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     TypoTolerance(enabled=False)
            >>>     await index.update_typo_tolerance()
        """
        url = f"{self._settings_url}/typo-tolerance"

        if is_pydantic_2():
            response = await self._http_requests.patch(url, typo_tolerance.model_dump(by_alias=True))  # type: ignore[attr-defined]
        else:  # pragma: no cover
            response = await self._http_requests.patch(url, typo_tolerance.dict(by_alias=True))  # type: ignore[attr-defined]

        return TaskInfo(**response.json())

    async def reset_typo_tolerance(self) -> TaskInfo:
        """Reset typo tolerance to default values.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_typo_tolerance()
        """
        url = f"{self._settings_url}/typo-tolerance"
        response = await self._http_requests.delete(url)

        return TaskInfo(**response.json())

    async def get_faceting(self) -> Faceting:
        """Get faceting for the index.

        Returns:

            Faceting for the index.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     faceting = await index.get_faceting()
        """
        url = f"{self._settings_url}/faceting"
        response = await self._http_requests.get(url)

        return Faceting(**response.json())

    async def update_faceting(self, faceting: Faceting) -> TaskInfo:
        """Partially update the faceting settings for an index.

        Returns:

            Task to track the action.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_faceting(faceting=Faceting(max_values_per_facet=100))
        """
        url = f"{self._settings_url}/faceting"

        if is_pydantic_2():
            response = await self._http_requests.patch(url, faceting.model_dump(by_alias=True))  # type: ignore[attr-defined]
        else:  # pragma: no cover
            response = await self._http_requests.patch(url, faceting.dict(by_alias=True))  # type: ignore[attr-defined]

        return TaskInfo(**response.json())

    async def reset_faceting(self) -> TaskInfo:
        """Reset an index's faceting settings to their default value.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_faceting()
        """
        url = f"{self._settings_url}/faceting"
        response = await self._http_requests.delete(url)

        return TaskInfo(**response.json())

    async def get_pagination(self) -> Pagination:
        """Get pagination settings for the index.

        Returns:

            Pagination for the index.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_async_client import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     pagination_settings = await index.get_pagination()
        """
        url = f"{self._settings_url}/pagination"
        response = await self._http_requests.get(url)

        return Pagination(**response.json())

    async def update_pagination(self, settings: Pagination) -> TaskInfo:
        """Partially update the pagination settings for an index.

        Returns:

            Task to track the action.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_python_async import Client
            >>> from meilisearch_python_async.models.settings import Pagination
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.update_pagination(settings=Pagination(max_total_hits=123))
        """
        url = f"{self._settings_url}/pagination"

        if is_pydantic_2():
            response = await self._http_requests.patch(url, settings.model_dump(by_alias=True))  # type: ignore[attr-defined]
        else:  # pragma: no cover
            response = await self._http_requests.patch(url, settings.dict(by_alias=True))  # type: ignore[attr-defined]

        return TaskInfo(**response.json())

    async def reset_pagination(self) -> TaskInfo:
        """Reset an index's pagination settings to their default value.

        Returns:

            The details of the task status.

        Raises:

            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the Meilisearch API returned an error.

        Examples:

            >>> from meilisearch_async_client import Client
            >>> async with Client("http://localhost.com", "masterKey") as client:
            >>>     index = client.index("movies")
            >>>     await index.reset_pagination()
        """
        url = f"{self._settings_url}/pagination"
        response = await self._http_requests.delete(url)

        return TaskInfo(**response.json())


def _batch(documents: list[dict], batch_size: int) -> Generator[list[dict], None, None]:
    total_len = len(documents)
    for i in range(0, total_len, batch_size):
        yield documents[i : i + batch_size]


def _raise_on_no_documents(
    documents: list[Any], document_type: str, directory_path: str | Path
) -> None:
    if not documents:
        raise MeilisearchError(f"No {document_type} files found in {directory_path}")


def _combine_documents(documents: list[list[Any]]) -> list[Any]:
    return [x for y in documents for x in y]


async def _load_documents_from_file(
    file_path: Path | str,
    csv_delimiter: str | None = None,
) -> list[dict[Any, Any]]:
    if isinstance(file_path, str):
        file_path = Path(file_path)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, partial(_validate_file_type, file_path))

    if file_path.suffix == ".csv":
        if (
            csv_delimiter
            and len(csv_delimiter) != 1
            or csv_delimiter
            and not csv_delimiter.isascii()
        ):
            raise ValueError("csv_delimiter must be a single ascii character")
        with open(file_path) as f:
            if csv_delimiter:
                documents = await loop.run_in_executor(
                    None, partial(DictReader, f, delimiter=csv_delimiter)
                )
            else:
                documents = await loop.run_in_executor(None, partial(DictReader, f))
            return list(documents)

    if file_path.suffix == ".ndjson":
        with open(file_path) as f:
            return [await loop.run_in_executor(None, partial(json.loads, x)) for x in f]

    async with aiofiles.open(file_path, mode="r") as f:  # type: ignore
        data = await f.read()  # type: ignore
        documents = await loop.run_in_executor(None, partial(json.loads, data))

        if not isinstance(documents, list):
            raise InvalidDocumentError("Meilisearch requires documents to be in a list")

        return documents


def _process_search_parameters(
    *,
    q: str | None = None,
    facet_name: str | None = None,
    facet_query: str | None = None,
    offset: int = 0,
    limit: int = 20,
    filter: str | list[str | list[str]] | None = None,
    facets: list[str] | None = None,
    attributes_to_retrieve: list[str] = ["*"],
    attributes_to_crop: list[str] | None = None,
    crop_length: int = 200,
    attributes_to_highlight: list[str] | None = None,
    sort: list[str] | None = None,
    show_matches_position: bool = False,
    highlight_pre_tag: str = "<em>",
    highlight_post_tag: str = "</em>",
    crop_marker: str = "...",
    matching_strategy: str = "all",
    hits_per_page: int | None = None,
    page: int | None = None,
    attributes_to_search_on: list[str] | None = None,
    show_ranking_score: bool = False,
    show_ranking_score_details: bool = False,
    vector: list[float] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "q": q,
        "offset": offset,
        "limit": limit,
        "filter": filter,
        "facets": facets,
        "attributesToRetrieve": attributes_to_retrieve,
        "attributesToCrop": attributes_to_crop,
        "cropLength": crop_length,
        "attributesToHighlight": attributes_to_highlight,
        "sort": sort,
        "showMatchesPosition": show_matches_position,
        "highlightPreTag": highlight_pre_tag,
        "highlightPostTag": highlight_post_tag,
        "cropMarker": crop_marker,
        "matchingStrategy": matching_strategy,
        "hitsPerPage": hits_per_page,
        "page": page,
        "attributesToSearchOn": attributes_to_search_on,
        "showRankingScore": show_ranking_score,
    }

    if facet_name:
        body["facetName"] = facet_name

    if facet_query:
        body["facetQuery"] = facet_query

    if show_ranking_score_details:
        body["showRankingScoreDetails"] = show_ranking_score_details

    if vector:
        body["vector"] = vector

    return body


def _validate_file_type(file_path: Path) -> None:
    if file_path.suffix not in (".json", ".csv", ".ndjson"):
        raise MeilisearchError("File must be a json, ndjson, or csv file")
