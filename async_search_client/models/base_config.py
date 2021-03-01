from pydantic import BaseModel

from async_search_client.utils.camel import to_camel


class BaseConfig(BaseModel):
    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
