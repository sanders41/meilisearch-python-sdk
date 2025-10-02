from __future__ import annotations

from camel_converter.pydantic_base import CamelBase


class Webhook(CamelBase):
    uuid: str
    url: str
    headers: dict[str, str] | None = None
    is_editable: bool


class Webhooks(CamelBase):
    results: list[Webhook]


class WebhookCreate(CamelBase):
    url: str
    headers: dict[str, str] | None = None


class WebhookUpdate(CamelBase):
    url: str | None = None
    headers: dict[str, str] | None = None
