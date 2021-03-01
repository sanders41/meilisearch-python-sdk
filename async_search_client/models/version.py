from datetime import datetime

from async_search_client.models.base_config import BaseConfig


class Version(BaseConfig):
    commit_sha: str
    build_date: datetime
    pkg_version: str
