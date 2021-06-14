from __future__ import annotations

import json
from asyncio import get_running_loop, sleep
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, AsyncGenerator, Optional
from urllib.parse import urlencode

import aiofiles
from httpx import AsyncClient

from async_search_client._http_requests import _HttpRequests
from async_search_client.errors import (
    MeiliSearchApiError,
    MeiliSearchError,
    MeiliSearchTimeoutError,
)
from async_search_client.models import (
    IndexStats,
    MeiliSearchSettings,
    SearchResults,
    UpdateId,
    UpdateStatus,
)


class Index:
    """Index class gives access to all indexes routes and child routes.

    https://docs.meilisearch.com/reference/api/indexes.html
    """

    def __init__(
        self,
        http_client: AsyncClient,
        uid: str,
        primary_key: Optional[str] = None,
        created_at: Optional[str | datetime] = None,
        updated_at: Optional[str | datetime] = None,
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
        self.created_at: Optional[datetime] = self._iso_to_date_time(created_at)
        self.updated_at: Optional[datetime] = self._iso_to_date_time(updated_at)
        self._http_requests = _HttpRequests(http_client)

    def __str__(self) -> str:
        return f"uid={self.uid}, primary_key={self.primary_key}, created_at={self.created_at}, updated_at={self.updated_at}"

    def __repr__(self) -> str:
        return f"uid={self.uid}, primary_key={self.primary_key}, created_at={self.created_at}, updated_at={self.updated_at}"

    async def delete(self) -> int:
        """Deletes the index.

        Returns:
            The status code returned from the server. 204 means the index was successfully deleted.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}"
        response = await self._http_requests.delete(url)
        return response.status_code

    async def delete_if_exists(self) -> bool:
        """Delete the index if it already exists.

        Returns:
            True if the index was deleted or False if not.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        try:
            await self.delete()
            return True
        except MeiliSearchApiError as error:
            if error.error_code != "index_not_found":
                raise error
            return False

    async def update(self, primary_key: str = None) -> Index:
        """Update the index primary key.

        Args:
            primary_key: The primary key of the documents. Defaults to None.

        Returns:
            An instance of the Index with the updated information.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        payload = {}
        if primary_key is not None:
            payload["primaryKey"] = primary_key

        url = f"indexes/{self.uid}"
        response = await self._http_requests.put(url, payload)
        self.primary_key = response.json()["primaryKey"]
        return self

    async def fetch_info(self) -> Index:
        """Gets the infromation about the index.

        Returns:
            An instance of the Index containing the retrieved information.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}"
        response = await self._http_requests.get(url)
        index_dict = response.json()
        self.primary_key = index_dict["primaryKey"]
        loop = get_running_loop()
        self.created_at = await loop.run_in_executor(
            None, partial(self._iso_to_date_time, index_dict["createdAt"])
        )
        self.updated_at = await loop.run_in_executor(
            None, partial(self._iso_to_date_time, index_dict["updatedAt"])
        )
        return self

    async def get_primary_key(self) -> Optional[str]:
        """Get the primary key.

        Returns:
            The primary key for the documents in the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        info = await self.fetch_info()
        return info.primary_key

    @classmethod
    async def create(
        cls, http_client: AsyncClient, uid: str, primary_key: Optional[str] = None
    ) -> Index:
        """Creates a new index.

        Args:
            An instance of the AsyncClient. This automatically gets passed by the
                Client when creating and Index instance.
            uid: The index's unique identifier.
            primary_key: The primary key of the documents. Defaults to None.

        Returns:
            An instance of Index containing the information of the newly created index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        if not primary_key:
            payload = {"uid": uid}
        else:
            payload = {"primaryKey": primary_key, "uid": uid}

        url = "indexes"
        response = await _HttpRequests(http_client).post(url, payload)
        index_dict = response.json()
        return cls(
            http_client=http_client,
            uid=index_dict["uid"],
            primary_key=index_dict["primaryKey"],
            created_at=index_dict["createdAt"],
            updated_at=index_dict["updatedAt"],
        )

    async def get_all_update_status(self) -> Optional[list[UpdateStatus]]:
        """Get all update status.

        Returns:
            A list of all enqueued and processed actions of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/updates"
        response = await self._http_requests.get(url)

        if not response.json():
            return None

        return [UpdateStatus(**x) for x in response.json()]

    async def get_update_status(self, update_id: int) -> UpdateStatus:
        """Gets an update status based on the update id.

        Args:
            update_id: Identifier of the update to retrieve.

        Returns:
            The details of the update status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/updates/{update_id}"
        response = await self._http_requests.get(url)

        return UpdateStatus(**response.json())

    async def wait_for_pending_update(
        self, update_id: int, timeout_in_ms: int = 5000, interval_in_ms: int = 50
    ) -> UpdateStatus:
        """Wait until MeiliSearch processes an update, and get its status.

        Args:
            update_id: Identifier of the update to retrieve.
            timeout_in_ms: Amount of time in milliseconds to wait before raising a
                MeiliSearchTimeoutError. Defaults to 5000.
            interval_in_ms: Time interval in miliseconds to sleep between requests. Defaults to 50.

        Returns:
            Details of the processed update status.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
            MeiliSearchTimeoutError: If the connection times out.
        """
        start_time = datetime.now()
        elapsed_time = 0.0
        while elapsed_time < timeout_in_ms:
            get_update = await self.get_update_status(update_id)
            if get_update.status != "enqueued":
                return get_update
            await sleep(interval_in_ms / 1000)
            time_delta = datetime.now() - start_time
            elapsed_time = time_delta.seconds * 1000 + time_delta.microseconds / 1000
        raise MeiliSearchTimeoutError(
            f"timeout of {timeout_in_ms}ms has exceeded on process {update_id} when waiting for pending update to resolve."
        )

    async def get_stats(self) -> IndexStats:
        """Get stats of the index.

        Returns:
            Stats about the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/stats"
        response = await self._http_requests.get(url)

        return IndexStats(**response.json())

    async def search(
        self,
        query: str,
        offset: int = 0,
        limit: int = 20,
        filters: Optional[str] = None,
        facet_filters: Optional[list[str | list[str]]] = None,
        facets_distribution: Optional[list[str]] = None,
        attributes_to_retrieve: list[str] = ["*"],
        attributes_to_crop: Optional[list[str]] = None,
        crop_length: int = 200,
        attributes_to_highlight: Optional[list[str]] = None,
        matches: bool = False,
    ) -> SearchResults:
        """Search the index.

        Args:
            query: String containing the word(s) to search
            offset: Number of documents to skip. Defaults to 0.
            limit: Maximum number of documents returned. Defaults to 20.
            filters: Filter queries by an attribute value. Defaults to None.
            facet_filters: Facet names and values to filter on. Defaults to None.
            facets_distribution: Facets for which to retrieve the matching count. Defaults to None.
            attributes_to_retrieve: Attributes to display in the returned documents.
                Defaults to ["*"].
            attributes_to_crop: Attributes whose values have to be cropped. Defaults to None.
            crop_length: Length used to crop field values. Defaults to 200.
            attributes_to_highlight: Attributes whose values will contain highlighted matching terms.
                Defaults to None.
            matches: Defines whether an object that contains information about the matches should be
                returned or not. Defaults to False.

        Returns:
            Results of the search

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        body = {
            "q": query,
            "offset": offset,
            "limit": limit,
            "filters": filters,
            "facetFilters": facet_filters,
            "facetsDistribution": facets_distribution,
            "attributesToRetrieve": attributes_to_retrieve,
            "attributesToCrop": attributes_to_crop,
            "cropLength": crop_length,
            "attributesToHighlight": attributes_to_highlight,
            "matches": matches,
        }
        url = f"indexes/{self.uid}/search"
        response = await self._http_requests.post(url, body=body)

        return SearchResults(**response.json())

    async def get_document(self, document_id: str) -> dict:
        """Get one document with given document identifier.

        Args:
            document_id: Unique identifier of the document.

        Returns:
            The document information

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/documents/{document_id}"
        response = await self._http_requests.get(url)
        return response.json()

    async def get_documents(
        self, offset: int = 0, limit: int = 20, attributes_to_retrieve: Optional[str] = None
    ) -> Optional[list[dict]]:
        """Get a batch documents from the index.

        Args:
            offset: Number of documents to skip. Defaults to 0.
            limit: Maximum number of documents returnedd. Defaults to 20.
            attributes_to_retrieve: Document attributes to show. If this value is None then all
                attributes are retrieved. Defaults to None.

        Returns:
            A list of documents.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        parameters: dict[str, Any] = {
            "offset": offset,
            "limit": limit,
        }

        if attributes_to_retrieve:
            parameters["attributesToRetrieve"] = attributes_to_retrieve

        url = f"indexes/{self.uid}/documents?{urlencode(parameters)}"
        response = await self._http_requests.get(url)

        if not response.json():
            return None

        return response.json()

    async def add_documents(
        self, documents: list[dict], primary_key: Optional[str] = None
    ) -> UpdateId:
        """Add documents to the index.

        Args:
            documents: List of documents.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/documents"
        if primary_key:
            formatted_primary_key = urlencode({"primaryKey": primary_key})
            url = f"{url}?{formatted_primary_key}"

        response = await self._http_requests.post(url, documents)
        return UpdateId(**response.json())

    async def add_documents_in_batches(
        self, documents: list[dict], batch_size: int = 1000, primary_key: Optional[str] = None
    ) -> list[UpdateId]:
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
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        update_ids: list[UpdateId] = []

        async for document_batch in self._batch(documents, batch_size):
            update_id = await self.add_documents(document_batch, primary_key)
            update_ids.append(update_id)

        return update_ids

    async def add_documents_from_file(
        self, file_path: Path | str, primary_key: Optional[str] = None
    ) -> UpdateId:
        """Add documents to the index from a json file.

        Args:
            file_path: Path to the json file.
            primary_key The primary key of the documents. This will be ignored if already set.
                Defaults to None.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        if isinstance(file_path, str):
            file_path = Path(file_path)

        loop = get_running_loop()
        await loop.run_in_executor(None, partial(self._validate_json_path, file_path))

        async with aiofiles.open(file_path, mode="r") as f:
            data = await f.read()
            documents = json.loads(data)

        return await self.add_documents(documents, primary_key=primary_key)

    async def add_documents_from_file_in_batches(
        self, file_path: Path | str, batch_size: int = 1000, primary_key: Optional[str] = None
    ) -> list[UpdateId]:
        """Adds documents form a json file in batches to reduce RAM usage with indexing.

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
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        if isinstance(file_path, str):
            file_path = Path(file_path)

        loop = get_running_loop()
        await loop.run_in_executor(None, partial(self._validate_json_path, file_path))

        async with aiofiles.open(file_path, mode="r") as f:
            data = await f.read()
            documents = json.loads(data)

        return await self.add_documents_in_batches(
            documents, batch_size=batch_size, primary_key=primary_key
        )

    async def update_documents(
        self, documents: list[dict], primary_key: Optional[str] = None
    ) -> UpdateId:
        """Update documents in the index.

        Args:
            documents: List of documents.
            primary_key: The primary key of the documents. This will be ignored if already set.
                Defaults to None.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/documents"
        if primary_key:
            formatted_primary_key = urlencode({"primaryKey": primary_key})
            url = f"{url}?{formatted_primary_key}"

        response = await self._http_requests.put(url, documents)
        return UpdateId(**response.json())

    async def update_documents_in_batches(
        self, documents: list[dict], batch_size: int = 1000, primary_key: Optional[str] = None
    ) -> list[UpdateId]:
        """Update documents in batches to reduce RAM usage with indexing.

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
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        update_ids: list[UpdateId] = []

        async for document_batch in self._batch(documents, batch_size):
            update_id = await self.update_documents(document_batch, primary_key)
            update_ids.append(update_id)

        return update_ids

    async def update_documents_from_file(
        self, file_path: Path | str, primary_key: Optional[str] = None
    ) -> UpdateId:
        """Add documents in the index from a json file.

        Args:
            file_path: Path to the json file.
            primary_key The primary key of the documents. This will be ignored if already set.
                Defaults to None.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        if isinstance(file_path, str):
            file_path = Path(file_path)

        loop = get_running_loop()
        await loop.run_in_executor(None, partial(self._validate_json_path, file_path))

        async with aiofiles.open(file_path, mode="r") as f:
            data = await f.read()
            documents = json.loads(data)

        return await self.update_documents(documents, primary_key=primary_key)

    async def update_documents_from_file_in_batches(
        self, file_path: Path | str, batch_size: int = 1000, primary_key: Optional[str] = None
    ) -> list[UpdateId]:
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
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        if isinstance(file_path, str):
            file_path = Path(file_path)

        loop = get_running_loop()
        await loop.run_in_executor(None, partial(self._validate_json_path, file_path))

        async with aiofiles.open(file_path, mode="r") as f:
            data = await f.read()
            documents = json.loads(data)

        return await self.update_documents_in_batches(
            documents, batch_size=batch_size, primary_key=primary_key
        )

    async def delete_document(self, document_id: str) -> UpdateId:
        """Delete one document from the index.

        Args:
            document_id: Unique identifier of the document.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/documents/{document_id}"
        response = await self._http_requests.delete(url)

        return UpdateId(**response.json())

    async def delete_documents(self, ids: list[str]) -> UpdateId:
        """Delete multiple documents from the index.

        Args:
            ids: List of unique identifiers of documents.

        Returns:
            List of update ids to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/documents/delete-batch"
        response = await self._http_requests.post(url, ids)

        return UpdateId(**response.json())

    async def delete_all_documents(self) -> UpdateId:
        """Delete all documents from the index.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/documents"
        response = await self._http_requests.delete(url)

        return UpdateId(**response.json())

    # GENERAL SETTINGS ROUTES

    async def get_settings(self) -> MeiliSearchSettings:
        """Get settings of the index.

        Returns:
            Settings of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings"
        response = await self._http_requests.get(url)

        return MeiliSearchSettings(**response.json())

    async def update_settings(self, body: MeiliSearchSettings) -> UpdateId:
        """Update settings of the index.

        Args:
            body: Settings of the index.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        body_dict = {k: v for k, v in body.dict(by_alias=True).items() if v is not None}

        url = f"indexes/{self.uid}/settings"
        response = await self._http_requests.post(url, body_dict)

        return UpdateId(**response.json())

    async def reset_settings(self) -> UpdateId:
        """Reset settings of the index to default values.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings"
        response = await self._http_requests.delete(url)

        return UpdateId(**response.json())

    # RANKING RULES SUB-ROUTES

    async def get_ranking_rules(self) -> list[str]:
        """Get ranking rules of the index.

        Returns:
            List containing the ranking rules of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/ranking-rules"
        response = await self._http_requests.get(url)

        return response.json()

    async def update_ranking_rules(self, ranking_rules: list[str]) -> UpdateId:
        """Update ranking rules of the index.

        Args:
            ranking_rules: List containing the ranking rules.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/ranking-rules"
        respose = await self._http_requests.post(url, ranking_rules)

        return UpdateId(**respose.json())

    async def reset_ranking_rules(self) -> UpdateId:
        """Reset ranking rules of the index to default values.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/ranking-rules"
        response = await self._http_requests.delete(url)

        return UpdateId(**response.json())

    # DISTINCT ATTRIBUTE SUB-ROUTES

    async def get_distinct_attribute(self) -> Optional[str]:
        """Get distinct attribute of the index.

        Returns:
            String containing the distinct attribute of the index. If no distinct attribute None
            is returned.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/distinct-attribute"
        response = await self._http_requests.get(url)

        if not response.json():
            None

        return response.json()

    async def update_distinct_attribute(self, body: str) -> UpdateId:
        """Update distinct attribute of the index.

        Args:
            body (str): [description]

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/distinct-attribute"
        response = await self._http_requests.post(url, body)

        return UpdateId(**response.json())

    async def reset_distinct_attribute(self) -> UpdateId:
        """Reset distinct attribute of the index to default values.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/distinct-attribute"
        response = await self._http_requests.delete(url)

        return UpdateId(**response.json())

    # SEARCHABLE ATTRIBUTES SUB-ROUTES

    async def get_searchable_attributes(self) -> list[str]:
        """Get searchable attributes of the index.

        Returns:
            List containing the searchable attributes of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/searchable-attributes"
        response = await self._http_requests.get(url)
        return response.json()

    async def update_searchable_attributes(self, body: list[str]) -> UpdateId:
        """Update searchable attributes of the index.

        Args:
            body: List containing the searchable attributes.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/searchable-attributes"
        response = await self._http_requests.post(url, body)

        return UpdateId(**response.json())

    async def reset_searchable_attributes(self) -> UpdateId:
        """Reset searchable attributes of the index to default values.

        Args:
            body: List containing the searchable attributes.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/searchable-attributes"
        response = await self._http_requests.delete(url)

        return UpdateId(**response.json())

    # DISPLAYED ATTRIBUTES SUB-ROUTES

    async def get_displayed_attributes(self) -> list[str]:
        """Get displayed attributes of the index.

        Returns:
            List containing the displayed attributes of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/displayed-attributes"
        response = await self._http_requests.get(url)
        return response.json()

    async def update_displayed_attributes(self, body: list[str]) -> UpdateId:
        """Update displayed attributes of the index.

        Args:
            body: List containing the displayed attributes.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/displayed-attributes"
        response = await self._http_requests.post(url, body)

        return UpdateId(**response.json())

    async def reset_displayed_attributes(self) -> UpdateId:
        """Reset displayed attributes of the index to default values.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/displayed-attributes"
        response = await self._http_requests.delete(url)

        return UpdateId(**response.json())

    # STOP WORDS SUB-ROUTES

    async def get_stop_words(self) -> Optional[list[str]]:
        """Get stop words of the index.

        Returns:
            List containing the stop words of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/stop-words"
        response = await self._http_requests.get(url)

        if not response.json():
            return None

        return response.json()

    async def update_stop_words(self, body: list[str]) -> UpdateId:
        """Update stop words of the index.

        Args:
            body: List containing the stop words of the index.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/stop-words"
        response = await self._http_requests.post(url, body)

        return UpdateId(**response.json())

    async def reset_stop_words(self) -> UpdateId:
        """Reset stop words of the index to default values.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/stop-words"
        response = await self._http_requests.delete(url)

        return UpdateId(**response.json())

    # SYNONYMS SUB-ROUTES

    async def get_synonyms(self) -> Optional[dict[str, list[str]]]:
        """Get synonyms of the index.

        Returns:
            The synonyms of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/synonyms"
        response = await self._http_requests.get(url)

        if not response.json():
            return None

        return response.json()

    async def update_synonyms(self, body: dict[str, list[str]]) -> UpdateId:
        """Update synonyms of the index.

        Args:
            body: The synonyms of the index.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/synonyms"
        response = await self._http_requests.post(url, body)

        return UpdateId(**response.json())

    async def reset_synonyms(self) -> UpdateId:
        """Reset synonyms of the index to default values.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/synonyms"
        response = await self._http_requests.delete(url)

        return UpdateId(**response.json())

    # ATTRIBUTES FOR FACETING SUB-ROUTES

    async def get_attributes_for_faceting(self) -> Optional[list[str]]:
        """Get attributes for faceting of the index.

        Returns:
            List containing the attributes for faceting of the index.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/attributes-for-faceting"
        response = await self._http_requests.get(url)

        if not response.json():
            return None

        return response.json()

    async def update_attributes_for_faceting(self, body: list[str]) -> UpdateId:
        """Update attributes for faceting of the index.

        Args:
            body: List containing the attributes for faceting.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/attributes-for-faceting"
        response = await self._http_requests.post(url, body)

        return UpdateId(**response.json())

    async def reset_attributes_for_faceting(self) -> UpdateId:
        """Reset attributes for faceting of the index to default values.

        Returns:
            Update id to track the action.

        Raises:
            MeilisearchCommunicationError: If there was an error communicating with the server.
            MeilisearchApiError: If the MeiliSearch API returned an error.
        """
        url = f"indexes/{self.uid}/settings/attributes-for-faceting"
        response = await self._http_requests.delete(url)

        return UpdateId(**response.json())

    @staticmethod
    def _iso_to_date_time(iso_date: Optional[datetime | str]) -> Optional[datetime]:
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
    async def _batch(documents: list[dict], batch_size: int) -> AsyncGenerator[list[dict], None]:
        total_len = len(documents)
        for i in range(0, total_len, batch_size):
            yield documents[i : i + batch_size]

    @staticmethod
    def _validate_json_path(file_path: Path) -> None:
        if file_path.suffix != ".json":
            raise MeiliSearchError("File must be a json file")
