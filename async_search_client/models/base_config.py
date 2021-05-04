from camel_converter import to_camel
from pydantic import BaseModel


class BaseConfig(BaseModel):
    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True
