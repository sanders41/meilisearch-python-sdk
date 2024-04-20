from datetime import datetime
from typing import Dict, List, Optional, Union
from warnings import warn

import pydantic
from camel_converter.pydantic_base import CamelBase

from meilisearch_python_sdk._utils import is_pydantic_2, iso_to_date_time
from meilisearch_python_sdk.models.index import IndexStats


class ClientStats(CamelBase):
    database_size: int
    last_update: Optional[datetime] = None
    indexes: Optional[Dict[str, IndexStats]] = None

    if is_pydantic_2():

        @pydantic.field_validator("last_update", mode="before")  # type: ignore[attr-defined]
        @classmethod
        def validate_last_update(cls, v: str) -> Union[datetime, None]:
            return iso_to_date_time(v)

    else:  # pragma: no cover
        warn(
            "The use of Pydantic less than version 2 is depreciated and will be removed in a future release",
            DeprecationWarning,
            stacklevel=2,
        )

        @pydantic.validator("last_update", pre=True)
        @classmethod
        def validate_last_update(cls, v: str) -> Union[datetime, None]:
            return iso_to_date_time(v)


class _KeyBase(CamelBase):
    uid: str
    name: Optional[str] = None
    description: str
    actions: List[str]
    indexes: List[str]
    expires_at: Optional[datetime] = None

    if is_pydantic_2():
        model_config = pydantic.ConfigDict(ser_json_timedelta="iso8601")  # type: ignore[typeddict-unknown-key]

        @pydantic.field_validator("expires_at", mode="before")  # type: ignore[attr-defined]
        @classmethod
        def validate_expires_at(cls, v: str) -> Union[datetime, None]:
            return iso_to_date_time(v)

    else:  # pragma: no cover
        warn(
            "The use of Pydantic less than version 2 is depreciated and will be removed in a future release",
            DeprecationWarning,
            stacklevel=2,
        )

        @pydantic.validator("expires_at", pre=True)
        @classmethod
        def validate_expires_at(cls, v: str) -> Union[datetime, None]:
            return iso_to_date_time(v)

        class Config:
            json_encoders = {
                datetime: lambda v: None
                if not v
                else (
                    f"{str(v).split('+')[0].replace(' ', 'T')}Z"
                    if "+" in str(v)
                    else f"{str(v).replace(' ', 'T')}Z"
                )
            }


class Key(_KeyBase):
    key: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    if is_pydantic_2():

        @pydantic.field_validator("created_at", mode="before")  # type: ignore[attr-defined]
        @classmethod
        def validate_created_at(cls, v: str) -> datetime:
            converted = iso_to_date_time(v)

            if not converted:  # pragma: no cover
                raise ValueError("created_at is required")

            return converted

        @pydantic.field_validator("updated_at", mode="before")  # type: ignore[attr-defined]
        @classmethod
        def validate_updated_at(cls, v: str) -> Union[datetime, None]:
            return iso_to_date_time(v)

    else:  # pragma: no cover
        warn(
            "The use of Pydantic less than version 2 is depreciated and will be removed in a future release",
            DeprecationWarning,
            stacklevel=2,
        )

        @pydantic.validator("created_at", pre=True)
        @classmethod
        def validate_created_at(cls, v: str) -> datetime:
            converted = iso_to_date_time(v)

            if not converted:
                raise ValueError("created_at is required")

            return converted

        @pydantic.validator("updated_at", pre=True)
        @classmethod
        def validate_updated_at(cls, v: str) -> Union[datetime, None]:
            return iso_to_date_time(v)


class KeyCreate(CamelBase):
    name: Optional[str] = None
    description: str
    actions: List[str]
    indexes: List[str]
    expires_at: Optional[datetime] = None

    if is_pydantic_2():
        model_config = pydantic.ConfigDict(ser_json_timedelta="iso8601")  # type: ignore[typeddict-unknown-key]

    else:  # pragma: no cover
        warn(
            "The use of Pydantic less than version 2 is depreciated and will be removed in a future release",
            DeprecationWarning,
            stacklevel=2,
        )

        class Config:
            json_encoders = {
                datetime: lambda v: None
                if not v
                else (
                    f"{str(v).split('+')[0].replace(' ', 'T')}Z"
                    if "+" in str(v)
                    else f"{str(v).replace(' ', 'T')}Z"
                )
            }


class KeyUpdate(CamelBase):
    key: str
    name: Optional[str] = None
    description: Optional[str] = None
    actions: Optional[List[str]] = None
    indexes: Optional[List[str]] = None
    expires_at: Optional[datetime] = None

    if is_pydantic_2():
        model_config = pydantic.ConfigDict(ser_json_timedelta="iso8601")  # type: ignore[typeddict-unknown-key]

    else:  # pragma: no cover
        warn(
            "The use of Pydantic less than version 2 is depreciated and will be removed in a future release",
            DeprecationWarning,
            stacklevel=2,
        )

        class Config:
            json_encoders = {
                datetime: lambda v: None
                if not v
                else (
                    f"{str(v).split('+')[0].replace(' ', 'T')}Z"
                    if "+" in str(v)
                    else f"{str(v).replace(' ', 'T')}Z"
                )
            }


class KeySearch(CamelBase):
    results: List[Key]
    offset: int
    limit: int
    total: int
