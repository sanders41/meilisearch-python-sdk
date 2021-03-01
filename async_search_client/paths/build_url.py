from typing import Optional, Union

from async_search_client.paths.valid_paths import Paths


def build_url(
    section: Paths, uid: Optional[str] = None, post_uid: Optional[Union[Paths, str]] = None
) -> str:
    url = section.value

    if uid:
        url = f"{url}/{uid}"

    if post_uid:
        if isinstance(post_uid, Paths):
            url = f"{url}/{post_uid.value}"
        else:
            url = f"{url}/{post_uid}"

    return url
