"""Smoke tests that the check classes work as pandera checks."""

import pandas as pd
import pandera.pandas as pa
import pytest

from crosscontract.contracts.schema.validation.checks import IsValidPrimaryKey


@pytest.fixture
def check() -> IsValidPrimaryKey:
    """A primary key check on 'id' with one existing key."""
    return IsValidPrimaryKey(label="primary key", columns=["id"], existing=[("c",)])


@pytest.fixture
def schema(check: IsValidPrimaryKey) -> pa.DataFrameSchema:
    """A pandera schema carrying the checks produced by the primary key check."""
    return pa.DataFrameSchema(
        columns={"id": pa.Column(str, nullable=True)},
        checks=check.to_pandera(),
    )


def test_to_pandera_returns_one_check_per_rule(check: IsValidPrimaryKey) -> None:
    assert len(check.to_pandera()) == 3


def test_valid_frame_passes(schema: pa.DataFrameSchema) -> None:
    df = pd.DataFrame({"id": ["a", "b"]})
    pd.testing.assert_frame_equal(schema.validate(df), df)


@pytest.mark.parametrize(
    "ids",
    [
        pytest.param(["a", "a"], id="duplicate"),
        pytest.param(["a", None], id="null"),
        pytest.param(["a", "c"], id="collides_with_existing"),
    ],
)
def test_invalid_frame_fails(schema: pa.DataFrameSchema, ids: list[str | None]) -> None:
    with pytest.raises(pa.errors.SchemaErrors):
        schema.validate(pd.DataFrame({"id": ids}), lazy=True)


def test_calling_the_check_marks_the_offending_rows(check: IsValidPrimaryKey) -> None:
    df = pd.DataFrame({"id": ["a", "a", "b", "c"]})
    assert check(df).tolist() == [False, False, True, False]
