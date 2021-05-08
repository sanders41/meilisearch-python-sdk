from camel_converter.pydantic_base import CamelBase


class Health(CamelBase):
    status: str
