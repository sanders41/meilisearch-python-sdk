from __future__ import annotations

from asyncio import sleep
from datetime import datetime
from typing import Any, Optional, Union
from urllib.parse import urlencode

from httpx import AsyncClient

from async_search_client._http_requests import HttpRequests
from async_search_client.errors import MeiliSearchTimeoutError
from async_search_client.models import (
    IndexStats,
    MeiliSearchSettings,
    SearchResults,
    UpdateId,
    UpdateStatus,
)
from async_search_client.paths import Paths, build_url


class Index:
    def __init__(self, http_client: AsyncClient, uid: str, primary_key: Optional[str] = None):
        self.http_client = http_client
        self.uid = uid
        self.primary_key = primary_key
        self._http_requests = HttpRequests(http_client)

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
        resonse = await HttpRequests(http_client).post(url, payload)
        index_dict = resonse.json()
        return cls(http_client, index_dict["uid"], index_dict["primaryKey"])

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
        facet_filters: Optional[Union[str, list[str]]] = None,
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

    async def update_documents(self, documents: list[dict]) -> UpdateId:
        url = url = build_url(Paths.INDEXES, self.uid, Paths.DOCUMENTS)

        response = await self._http_requests.put(url, documents)
        return UpdateId(**response.json())

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

    async def update_ranking_rules(self, body: MeiliSearchSettings) -> UpdateId:
        respose = await self._http_requests.post(self._settings_url_for(Paths.RANKING_RULES), body)

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

    def _settings_url_for(self, sub_route: Paths) -> str:
        return build_url(Paths.INDEXES, self.uid, f"{Paths.SETTINGS.value}/{sub_route.value}")
