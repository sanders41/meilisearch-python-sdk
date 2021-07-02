from datetime import date

from camel_converter.pydantic_base import CamelBase


class Version(CamelBase):
    commit_sha: str
    commit_date: date
    pkg_version: str
