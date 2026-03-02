from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import jwt

from meilisearch_python_sdk.errors import InvalidRestriction
from meilisearch_python_sdk.json_handler import BuiltinHandler, OrjsonHandler
from meilisearch_python_sdk.models.client import (
    Key,
)
from meilisearch_python_sdk.types import JsonDict

if TYPE_CHECKING:
    from meilisearch_python_sdk.types import JsonMapping


class BaseClient:
    def __init__(
        self,
        api_key: str | None = None,
        custom_headers: dict[str, str] | None = None,
        json_handler: BuiltinHandler | OrjsonHandler | None = None,
    ) -> None:
        self.json_handler = json_handler if json_handler else BuiltinHandler()
        self._headers: dict[str, str] | None = None
        if api_key:
            self._headers = {"Authorization": f"Bearer {api_key}"}

        if custom_headers:
            if self._headers:
                self._headers.update(custom_headers)
            else:
                self._headers = custom_headers

    def generate_tenant_token(
        self,
        search_rules: JsonMapping | list[str],
        *,
        api_key: Key,
        expires_at: datetime | None = None,
    ) -> str:
        """Generates a JWT token to use for searching.

        Args:
            search_rules: Contains restrictions to use for the token. The default rules used for
                the API key used for signing can be used by setting searchRules to ["*"]. If "indexes"
                is included it must be equal to or more restrictive than the key used to generate the
                token.
            api_key: The API key to use to generate the token.
            expires_at: The timepoint at which the token should expire. If value is provided it
                should be a UTC time in the future. Default = None.

        Returns:
            A JWT token

        Raises:
            InvalidRestriction: If the restrictions are less strict than the permissions allowed
                in the API key.
            KeyNotFoundError: If no API search key is found.

        Examples:
            Async:

            >>> from datetime import datetime, timedelta, timezone
            >>> from meilisearch_python_sdk import AsyncClient
            >>>
            >>> expires_at = datetime.now(tz=timezone.utc) + timedelta(days=7)
            >>>
            >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
            >>>     token = client.generate_tenant_token(
            >>>         search_rules = ["*"], api_key=api_key, expires_at=expires_at
            >>>     )

            Sync:

            >>> from datetime import datetime, timedelta, timezone
            >>> from meilisearch_python_sdk import Client
            >>>
            >>> expires_at = datetime.now(tz=timezone.utc) + timedelta(days=7)
            >>>
            >>> with Client("http://localhost.com", "masterKey") as client:
            >>>     token = client.generate_tenant_token(
            >>>         search_rules = ["*"], api_key=api_key, expires_at=expires_at
            >>>     )
        """
        if isinstance(search_rules, dict) and search_rules.get("indexes"):
            for index in search_rules["indexes"]:
                if api_key.indexes != ["*"] and index not in api_key.indexes:
                    raise InvalidRestriction(
                        "Invalid index. The token cannot be less restrictive than the API key"
                    )

        payload: JsonDict = {"searchRules": search_rules}

        payload["apiKeyUid"] = api_key.uid
        if expires_at:
            if expires_at <= datetime.now(tz=timezone.utc):
                raise ValueError("expires_at must be a time in the future")

            payload["exp"] = int(datetime.timestamp(expires_at))

        return jwt.encode(payload, api_key.key, algorithm="HS256")
