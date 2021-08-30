from datetime import datetime

from camel_converter.pydantic_base import CamelBase


class Version(CamelBase):
    commit_sha: str
    commit_date: datetime
    pkg_version: str
