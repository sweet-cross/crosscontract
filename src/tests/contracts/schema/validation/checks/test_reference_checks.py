import pandas as pd
import pandera.pandas as pa
import pytest
from pydantic import ValidationError

from crosscontract.contracts.schema.validation.checks import (
    BaseCheck,
    IsNotIn,
    IsNotNull,
    IsUnique,
    IsValidPrimaryKey,
)

# IsValidPrimaryKey is a composite: it answers as one predicate when called, and
# unpacks into one pandera check per sub-rule so a report says which rule broke.
# Both paths are exercised here, on the same cases, because they are built
# separately and must agree.


# ---------------------------------------------------------------------------
# The predicate
# ---------------------------------------------------------------------------
class TestIsValidPrimaryKey:
    @pytest.fixture
    def check(self) -> IsValidPrimaryKey:
        return IsValidPrimaryKey(
            label="primary key", columns=["id"], existing=[("c",)]
        )

    def test_valid_keys_pass(self, check: IsValidPrimaryKey):
        """Rows pass when they are non-null, unique, and absent from the
        existing keys."""
        df = pd.DataFrame({"id": ["a", "b"]})
        assert check(df).tolist() == [True, True]

    def test_duplicate_fails_every_occurrence(self, check: IsValidPrimaryKey):
        """A key repeated within the data fails on every row it appears in."""
        df = pd.DataFrame({"id": ["a", "a", "b"]})
        assert check(df).tolist() == [False, False, True]

    def test_null_fails(self, check: IsValidPrimaryKey):
        """A primary key may not be null."""
        df = pd.DataFrame({"id": ["a", None]})
        assert check(df).tolist() == [True, False]

    def test_collision_with_an_existing_key_fails(self, check: IsValidPrimaryKey):
        """A key already stored elsewhere fails even though it is unique within
        the data at hand."""
        df = pd.DataFrame({"id": ["a", "c"]})
        assert check(df).tolist() == [True, False]

    def test_without_existing_keys_the_data_is_still_checked(self):
        """Supplying no existing keys removes only the comparison against them —
        uniqueness and non-nullness within the data still hold."""
        check = IsValidPrimaryKey(label="primary key", columns=["id"])
        assert check(pd.DataFrame({"id": ["a", "b"]})).tolist() == [True, True]
        assert check(pd.DataFrame({"id": ["a", "a"]})).tolist() == [False, False]

    def test_composite_key_is_judged_jointly(self):
        """A value repeating in one column is fine as long as the combination
        stays unique."""
        check = IsValidPrimaryKey(label="primary key", columns=["x", "y"])
        assert check(pd.DataFrame({"x": ["a", "a"], "y": [1, 2]})).tolist() == [
            True,
            True,
        ]
        assert check(pd.DataFrame({"x": ["a", "a"], "y": [1, 1]})).tolist() == [
            False,
            False,
        ]

    def test_existing_keys_must_be_as_wide_as_the_columns(self):
        """A two-wide existing key against a one-column primary key would
        collide with nothing and silently pass every row, so it is rejected at
        construction."""
        with pytest.raises(ValidationError):
            IsValidPrimaryKey(
                label="primary key", columns=["id"], existing=[("a", 1)]
            )


# ---------------------------------------------------------------------------
# The pandera conversion
# ---------------------------------------------------------------------------
class TestToPandera:
    @pytest.fixture
    def check(self) -> IsValidPrimaryKey:
        return IsValidPrimaryKey(
            label="primary key", columns=["id"], existing=[("c",)]
        )

    @pytest.fixture
    def schema(self, check: IsValidPrimaryKey) -> pa.DataFrameSchema:
        return pa.DataFrameSchema(
            columns={"id": pa.Column(str, nullable=True)},
            checks=check.to_pandera(),
        )

    def test_unpacks_into_one_check_per_rule(self, check: IsValidPrimaryKey):
        """The composite reports its three rules separately rather than as one
        opaque failure."""
        assert len(check.to_pandera()) == 3

    @pytest.mark.parametrize(
        ("ids", "expected_check"),
        [
            pytest.param(["a", "a"], IsUnique, id="duplicate"),
            pytest.param(["a", None], IsNotNull, id="null"),
            pytest.param(["a", "c"], IsNotIn, id="collides_with_existing"),
        ],
    )
    def test_the_violated_rule_is_the_one_reported(
        self,
        check: IsValidPrimaryKey,
        schema: pa.DataFrameSchema,
        ids: list[str | None],
        expected_check: type[BaseCheck],
    ):
        """Each way of breaking a primary key is reported by the sub-check that
        owns it, and by that sub-check alone. Pandera identifies a check by its
        failure message, so that message is what makes the failure legible."""
        with pytest.raises(pa.errors.SchemaErrors) as exc_info:
            schema.validate(pd.DataFrame({"id": ids}), lazy=True)
        expected_message = expected_check(
            label=check.label, columns=check.columns
        ).failure_message()
        reported = exc_info.value.failure_cases["check"].astype(str)
        assert set(reported) == {expected_message}
