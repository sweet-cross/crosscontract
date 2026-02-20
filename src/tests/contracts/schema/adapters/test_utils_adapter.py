from datetime import UTC, datetime

import pytest

from crosscontract.contracts.schema.adapters.utils import parse_datetime


def test_parse_datetime():
    assert parse_datetime("2023-01-01 00:00", "%Y-%m-%d %H:%M") == datetime(
        2023, 1, 1, 0, 0, tzinfo=UTC
    )
    assert parse_datetime(datetime(2023, 1, 1, 0, 0), "%Y-%m-%d %H:%M") == datetime(
        2023, 1, 1, 0, 0, tzinfo=UTC
    )
    assert parse_datetime(
        datetime(2023, 1, 1, 0, 0, tzinfo=UTC), "%Y-%m-%d %H:%M"
    ) == datetime(2023, 1, 1, 0, 0, tzinfo=UTC)
    assert parse_datetime(None, "%Y-%m-%d %H:%M") is None
    with pytest.raises(ValueError):
        parse_datetime(12, "%Y-%m-%d %H:%M")
