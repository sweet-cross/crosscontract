import pandas as pd
import pytest

from crosscontract.contracts import BaseContract
from tests.conftest import target_contract


def bundle(*rows: tuple[str, str, int, float]) -> pd.DataFrame:
    """Build a submission frame according to the submission contract's schema.

    Args:
        *rows (tuple[str, str, int, float]): One tuple per row, holding
            `variable`, `country`, `year` and `value`.

    Returns:
        pd.DataFrame: The frame, with `year` as a nullable integer column.
    """
    return pd.DataFrame(
        list(rows), columns=["variable", "country", "year", "value"]
    ).astype({"year": "Int64"})


@pytest.fixture
def bad_contract_a() -> BaseContract:
    """Return a `contract_a` whose `region` the target's rows cannot satisfy."""
    return target_contract(
        "contract_a",
        [
            {"name": "region", "type": "integer"},
            {"name": "year", "type": "integer"},
            {"name": "value", "type": "number"},
        ],
    )


@pytest.fixture
def bad_contract_c() -> BaseContract:
    """Return a `contract_c` whose `country` the target's rows cannot satisfy."""
    return target_contract(
        "contract_c",
        [
            {"name": "country", "type": "integer"},
            {"name": "period", "type": "integer"},
            {"name": "value", "type": "number"},
        ],
    )
