from datetime import datetime
from typing import Union

from camel_converter.pydantic_base import CamelBase


class Version(CamelBase):
    commit_sha: str
    commit_date: Union[datetime, str]
    pkg_version: str
