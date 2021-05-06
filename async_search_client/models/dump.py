from camel_converter.pydantic_base import CamelBase


class DumpInfo(CamelBase):
    uid: str
    status: str
