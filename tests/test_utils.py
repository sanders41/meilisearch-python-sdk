from datetime import datetime

import pytest

from meilisearch_python_async._utils import is_pydantic_2, iso_to_date_time


def test_is_pydantic_2():
    assert is_pydantic_2() is True


@pytest.mark.parametrize(
    "iso_date, expected",
    [
        ("2021-05-11T03:12:22.563960100Z", datetime(2021, 5, 11, 3, 12, 22, 563960)),
        (datetime(2021, 5, 11, 3, 12, 22, 563960), datetime(2021, 5, 11, 3, 12, 22, 563960)),
        (None, None),
    ],
)
def test_iso_to_date_time(iso_date, expected):
    converted = iso_to_date_time(iso_date)

    assert converted == expected


def test_iso_to_date_time_invalid_format():
    with pytest.raises(ValueError):
        iso_to_date_time("2023-07-13T23:37:20Z")
