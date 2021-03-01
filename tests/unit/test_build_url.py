import pytest

from async_search_client.paths import Paths, build_url


@pytest.mark.parametrize(
    "section, uid, post_uid, expected",
    [
        (
            Paths.INDEXES,
            "testuid",
            Paths.DOCUMENTS,
            f"{Paths.INDEXES.value}/testuid/{Paths.DOCUMENTS.value}",
        ),
        (Paths.INDEXES, None, None, Paths.INDEXES.value),
        (Paths.INDEXES, "testuid", None, f"{Paths.INDEXES.value}/testuid"),
        (Paths.INDEXES, "testuid", "teststring", f"{Paths.INDEXES.value}/testuid/teststring"),
    ],
)
def test_buld_url(section, uid, post_uid, expected):
    got = build_url(section, uid, post_uid)

    assert got == expected
