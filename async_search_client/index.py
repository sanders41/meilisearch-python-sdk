from __future__ import annotations

import json
from asyncio import sleep
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional
from urllib.parse import urlencode

import aiofiles
from httpx import AsyncClient

from async_search_client._http_requests import HttpRequests
from async_search_client.errors import MeiliSearchError, MeiliSearchTimeoutError
from async_search_client.models import (
    IndexStats,
    MeiliSearchSettings,
    SearchResults,
    UpdateId,
    UpdateStatus,
)
from async_search_client.paths import Paths, build_url


class Index:
    def __init__(
        self,
        http_client: AsyncClient,
        uid: str,
        primary_key: Optional[str] = None,
        created_at: Optional[str | datetime] = None,
        updated_at: Optional[str | datetime] = None,
    ):
        self.http_client = http_client
        self.uid = uid
        self.primary_key = primary_key
        self.created_at: Optional[datetime] = self._iso_to_date_time(created_at)
        self.updated_at: Optional[datetime] = self._iso_to_date_time(updated_at)
        self._http_requests = HttpRequests(http_client)

    def __str__(self) -> str:
        return f"uid={self.uid}, primary_key={self.primary_key}, created_at={self.created_at}, updated_at={self.updated_at}"

    def __repr__(self) -> str:
        return f"uid={self.uid}, primary_key={self.primary_key}, created_at={self.created_at}, updated_at={self.updated_at}"

    async def delete(self) -> int:
        url = build_url(Paths.INDEXES, self.uid)
        response = await self._http_requests.delete(url)
        return response.status_code

    async def update(self, primary_key: str = None) -> Index:
        """
        Update the index primary-key.
        """
        payload = {}
        if primary_key is not None:
            payload["primaryKey"] = primary_key
        url = build_url(Paths.INDEXES, self.uid)
        response = await self._http_requests.put(url, payload)
        self.primary_key = response.json()["primaryKey"]
        return self

    async def fetch_info(self) -> Index:
        url = build_url(Paths.INDEXES, self.uid)
        response = await self._http_requests.get(url)
        index_dict = response.json()
        self.primary_key = index_dict["primaryKey"]
        self.created_at = self._iso_to_date_time(index_dict["createdAt"])
        self.updated_at = self._iso_to_date_time(index_dict["updatedAt"])
        return self

    async def get_primary_key(self) -> Optional[str]:
        info = await self.fetch_info()
        return info.primary_key

    @classmethod
    async def create(
        cls, http_client: AsyncClient, uid: str, primary_key: Optional[str] = None
    ) -> Index:
        if not primary_key:
            payload = {"uid": uid}
        else:
            payload = {"primaryKey": primary_key, "uid": uid}

        url = build_url(Paths.INDEXES)
        response = await HttpRequests(http_client).post(url, payload)
        index_dict = response.json()
        return cls(
            http_client=http_client,
            uid=index_dict["uid"],
            primary_key=index_dict["primaryKey"],
            created_at=index_dict["createdAt"],
            updated_at=index_dict["updatedAt"],
        )

    async def get_all_update_status(self) -> Optional[list[UpdateStatus]]:
        url = build_url(Paths.INDEXES, self.uid, Paths.UPDATES)
        response = await self._http_requests.get(url)

        if not response.json():
            return None

        return [UpdateStatus(**x) for x in response.json()]

    async def get_update_status(self, update_id: int) -> UpdateStatus:
        url = build_url(Paths.INDEXES, self.uid, f"{Paths.UPDATES.value}/{update_id}")
        response = await self._http_requests.get(url)

        return UpdateStatus(**response.json())

    async def wait_for_pending_update(
        self, update_id: int, timeout_in_ms: int = 5000, interval_in_ms: int = 50
    ) -> UpdateStatus:
        """
        Wait until MeiliSearch processes an update, and get its status.

        update_id: identifier of the update to retrieve
        timeout_in_ms (optional): time the method should wait before raising a MeiliSearchTimeoutError
        interval_in_ms (optional): time interval the method should wait (sleep) between requests
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
        url = build_url(Paths.INDEXES, self.uid, Paths.STATS)
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
        url = url = build_url(Paths.INDEXES, self.uid, Paths.SEARCH)
        response = await self._http_requests.post(url, body=body)

        return SearchResults(**response.json())

    async def get_document(self, document_id: str) -> dict:
        url = url = build_url(Paths.INDEXES, self.uid, f"{Paths.DOCUMENTS.value}/{document_id}")
        response = await self._http_requests.get(url)
        return response.json()

    async def get_documents(
        self, offset: int = 0, limit: int = 20, attributes_to_retrieve: Optional[str] = None
    ) -> Optional[list[dict]]:
        parameters: dict[str, Any] = {
            "offset": offset,
            "limit": limit,
        }

        if attributes_to_retrieve:
            parameters["attributesToRetrieve"] = attributes_to_retrieve

        url = build_url(Paths.INDEXES, self.uid, f"{Paths.DOCUMENTS.value}?{urlencode(parameters)}")
        response = await self._http_requests.get(url)

        if not response.json():
            return None

        return response.json()

    async def add_documents(
        self, documents: list[dict], primary_key: Optional[str] = None
    ) -> UpdateId:
        url = build_url(Paths.INDEXES, self.uid, Paths.DOCUMENTS)
        if primary_key:
            formatted_primary_key = urlencode({"primaryKey": primary_key})
            url = f"{url}?{formatted_primary_key}"

        response = await self._http_requests.post(url, documents)
        return UpdateId(**response.json())

    async def add_documents_in_batches(
        self, documents: list[dict], batch_size: int = 1000, primary_key: Optional[str] = None
    ) -> list[UpdateId]:
        """
        Splits documents into batches to reduce RAM usage with indexing.
        """

        def batch(documents: list[dict], batch_size: int) -> Generator[list[dict], None, None]:
            total_len = len(documents)
            for i in range(0, total_len, batch_size):
                yield documents[i : i + batch_size]

        update_ids: list[UpdateId] = []

        for document_batch in batch(documents, batch_size):
            update_id = await self.add_documents(document_batch, primary_key)
            update_ids.append(update_id)

        return update_ids

    async def add_documents_from_file(
        self, file_path: Path | str, primary_key: Optional[str] = None
    ) -> UpdateId:
        """
        Add documents to the index from a json file.
        """

        if isinstance(file_path, str):
            file_path = Path(file_path)

        self._validate_json_path(file_path)

        async with aiofiles.open(file_path, mode="r") as f:
            data = await f.read()
            documents = json.loads(data)

        return await self.add_documents(documents, primary_key=primary_key)

    async def add_documents_from_file_in_batches(
        self, file_path: Path | str, batch_size: int = 1000, primary_key: Optional[str] = None
    ) -> list[UpdateId]:
        """
        Add documents to the index from a json file in batches to reduce RAM usage.
        """

        if isinstance(file_path, str):
            file_path = Path(file_path)

        self._validate_json_path(file_path)

        async with aiofiles.open(file_path, mode="r") as f:
            data = await f.read()
            documents = json.loads(data)

        return await self.add_documents_in_batches(
            documents, batch_size=batch_size, primary_key=primary_key
        )

    async def update_documents(
        self, documents: list[dict], primary_key: Optional[str] = None
    ) -> UpdateId:
        url = url = build_url(Paths.INDEXES, self.uid, Paths.DOCUMENTS)
        if primary_key:
            formatted_primary_key = urlencode({"primaryKey": primary_key})
            url = f"{url}?{formatted_primary_key}"

        response = await self._http_requests.put(url, documents)
        return UpdateId(**response.json())

    async def update_documents_from_file(
        self, file_path: Path | str, primary_key: Optional[str] = None
    ) -> UpdateId:
        """
        Update documents to the index from a json file.
        """

        if isinstance(file_path, str):
            file_path = Path(file_path)

        self._validate_json_path(file_path)

        async with aiofiles.open(file_path, mode="r") as f:
            data = await f.read()
            documents = json.loads(data)

        return await self.update_documents(documents, primary_key=primary_key)

    async def delete_document(self, document_id: str) -> UpdateId:
        url = build_url(Paths.INDEXES, self.uid, f"{Paths.DOCUMENTS.value}/{document_id}")
        response = await self._http_requests.delete(url)

        return UpdateId(**response.json())

    async def delete_documents(self, ids: list[str]) -> UpdateId:
        url = build_url(Paths.INDEXES, self.uid, f"{Paths.DOCUMENTS.value}/delete-batch")
        response = await self._http_requests.post(url, ids)

        return UpdateId(**response.json())

    async def delete_all_documents(self) -> UpdateId:
        url = build_url(Paths.INDEXES, self.uid, Paths.DOCUMENTS)
        response = await self._http_requests.delete(url)

        return UpdateId(**response.json())

    # GENERAL SETTINGS ROUTES

    async def get_settings(self) -> MeiliSearchSettings:
        url = build_url(Paths.INDEXES, self.uid, Paths.SETTINGS)
        response = await self._http_requests.get(url)

        return MeiliSearchSettings(**response.json())

    async def update_settings(self, body: MeiliSearchSettings) -> UpdateId:
        body_dict = {k: v for k, v in body.dict(by_alias=True).items() if v is not None}

        url = build_url(Paths.INDEXES, self.uid, Paths.SETTINGS)
        response = await self._http_requests.post(url, body_dict)

        return UpdateId(**response.json())

    async def reset_settings(self) -> UpdateId:
        url = build_url(Paths.INDEXES, self.uid, Paths.SETTINGS)
        response = await self._http_requests.delete(url)

        return UpdateId(**response.json())

    # RANKING RULES SUB-ROUTES

    async def get_ranking_rules(self) -> list[str]:
        response = await self._http_requests.get(self._settings_url_for(Paths.RANKING_RULES))

        return response.json()

    async def update_ranking_rules(self, ranking_rules: list[str]) -> UpdateId:
        respose = await self._http_requests.post(
            self._settings_url_for(Paths.RANKING_RULES), ranking_rules
        )

        return UpdateId(**respose.json())

    async def reset_ranking_rules(self) -> UpdateId:
        response = await self._http_requests.delete(
            self._settings_url_for(Paths.RANKING_RULES),
        )

        return UpdateId(**response.json())

    # DISTINCT ATTRIBUTE SUB-ROUTES

    async def get_distinct_attribute(self) -> Optional[str]:
        response = await self._http_requests.get(self._settings_url_for(Paths.DISTINCT_ATTRIBUTE))

        if not response.json():
            None

        return response.json()

    async def update_distinct_attribute(self, body: str) -> UpdateId:
        response = await self._http_requests.post(
            self._settings_url_for(Paths.DISTINCT_ATTRIBUTE), body
        )

        return UpdateId(**response.json())

    async def reset_distinct_attribute(self) -> UpdateId:
        response = await self._http_requests.delete(
            self._settings_url_for(Paths.DISTINCT_ATTRIBUTE),
        )

        return UpdateId(**response.json())

    # SEARCHABLE ATTRIBUTES SUB-ROUTES

    async def get_searchable_attributes(self) -> list[str]:
        response = await self._http_requests.get(
            self._settings_url_for(Paths.SEARCHABLE_ATTRIBUTES)
        )
        return response.json()

    async def update_searchable_attributes(self, body: list[str]) -> UpdateId:
        response = await self._http_requests.post(
            self._settings_url_for(Paths.SEARCHABLE_ATTRIBUTES), body
        )

        return UpdateId(**response.json())

    async def reset_searchable_attributes(self) -> UpdateId:
        response = await self._http_requests.delete(
            self._settings_url_for(Paths.SEARCHABLE_ATTRIBUTES),
        )

        return UpdateId(**response.json())

    # DISPLAYED ATTRIBUTES SUB-ROUTES

    async def get_displayed_attributes(self) -> list[str]:
        response = await self._http_requests.get(self._settings_url_for(Paths.DISPLAYED_ATTRIBUTES))
        return response.json()

    async def update_displayed_attributes(self, body: list[str]) -> UpdateId:
        response = await self._http_requests.post(
            self._settings_url_for(Paths.DISPLAYED_ATTRIBUTES), body
        )

        return UpdateId(**response.json())

    async def reset_displayed_attributes(self) -> UpdateId:
        response = await self._http_requests.delete(
            self._settings_url_for(Paths.DISPLAYED_ATTRIBUTES),
        )

        return UpdateId(**response.json())

    # STOP WORDS SUB-ROUTES

    async def get_stop_words(self) -> Optional[list[str]]:
        response = await self._http_requests.get(self._settings_url_for(Paths.STOP_WORDS))

        if not response.json():
            return None

        return response.json()

    async def update_stop_words(self, body: list[str]) -> UpdateId:
        response = await self._http_requests.post(self._settings_url_for(Paths.STOP_WORDS), body)

        return UpdateId(**response.json())

    async def reset_stop_words(self) -> UpdateId:
        response = await self._http_requests.delete(
            self._settings_url_for(Paths.STOP_WORDS),
        )

        return UpdateId(**response.json())

    # SYNONYMS SUB-ROUTES

    async def get_synonyms(self) -> Optional[dict[str, list[str]]]:
        response = await self._http_requests.get(self._settings_url_for(Paths.SYNONYMS))

        if not response.json():
            return None

        return response.json()

    async def update_synonyms(self, body: dict[str, list[str]]) -> UpdateId:
        response = await self._http_requests.post(self._settings_url_for(Paths.SYNONYMS), body)

        return UpdateId(**response.json())

    async def reset_synonyms(self) -> UpdateId:
        response = await self._http_requests.delete(
            self._settings_url_for(Paths.SYNONYMS),
        )

        return UpdateId(**response.json())

    # ATTRIBUTES FOR FACETING SUB-ROUTES

    async def get_attributes_for_faceting(self) -> Optional[list[str]]:
        response = await self._http_requests.get(
            self._settings_url_for(Paths.ATTRIBUTES_FOR_FACETING)
        )

        if not response.json():
            return None

        return response.json()

    async def update_attributes_for_faceting(self, body: list[str]) -> UpdateId:
        response = await self._http_requests.post(
            self._settings_url_for(Paths.ATTRIBUTES_FOR_FACETING), body
        )

        return UpdateId(**response.json())

    async def reset_attributes_for_faceting(self) -> UpdateId:
        response = await self._http_requests.delete(
            self._settings_url_for(Paths.ATTRIBUTES_FOR_FACETING),
        )

        return UpdateId(**response.json())

    @staticmethod
    def _iso_to_date_time(iso_date: Optional[datetime | str]) -> Optional[datetime]:
        """
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

    def _settings_url_for(self, sub_route: Paths) -> str:
        return build_url(Paths.INDEXES, self.uid, f"{Paths.SETTINGS.value}/{sub_route.value}")

    @staticmethod
    def _validate_json_path(file_path: Path) -> None:
        if file_path.suffix != ".json":
            raise MeiliSearchError("File must be a json file")
