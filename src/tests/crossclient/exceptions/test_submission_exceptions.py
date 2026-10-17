import pandas as pd
import pytest

from crosscontract import TargetValidationError, UnclaimedRowsError
from crosscontract.contracts.schema import SchemaValidationError, TableSchema


def _schema_error(values: list) -> SchemaValidationError:
    """Produce a real validation failure by validating a bad frame.

    Constructing `SchemaValidationError` bare carries no pandera errors, so its
    `to_list()` is empty and the flattening below would prove nothing.
    """
    schema = TableSchema.model_validate({"fields": [{"name": "id", "type": "integer"}]})
    with pytest.raises(SchemaValidationError) as exc_info:
        schema.validate_dataframe(pd.DataFrame({"id": values}))
    return exc_info.value


class TestTargetValidationError:
    @pytest.fixture
    def sub_errors(self) -> dict[str, SchemaValidationError]:
        return {"t_a": _schema_error(["x"]), "t_b": _schema_error(["y", "z"])}

    @pytest.fixture
    def error(self, sub_errors) -> TargetValidationError:
        return TargetValidationError(sub_errors)

    def test_errors_are_exposed_unchanged(self, error, sub_errors):
        assert error.errors == sub_errors

    def test_message_names_the_failing_targets(self, error):
        assert "t_a" in str(error)
        assert "t_b" in str(error)

    def test_to_list_flattens_every_target(self, error, sub_errors):
        """No row is lost or added, and each one names its target."""
        rows = error.to_list()
        assert len(rows) == sum(len(e.to_list()) for e in sub_errors.values())
        assert {row["target"] for row in rows} == {"t_a", "t_b"}

    def test_to_pandas_is_one_flat_frame(self, error, sub_errors):
        """Filtering by target reproduces that target's own report.

        `check_dtype=False` because the combined frame infers dtypes across all
        targets, so a column can widen to `object` where a single target's would
        not have.
        """
        df = error.to_pandas()
        assert "target" in df.columns

        one_target = (
            df[df["target"] == "t_a"].drop(columns="target").reset_index(drop=True)
        )
        pd.testing.assert_frame_equal(
            one_target, sub_errors["t_a"].to_pandas(), check_dtype=False
        )

    def test_max_errors_none_is_unchanged(self, error):
        """Without `max_errors`, the full flattened report comes back."""
        assert error.to_list(max_errors=None) == error.to_list()
        assert all("count" not in row for row in error.to_list())

    def test_max_errors_limits_each_target(self):
        """Each target's report is condensed and limited on its own."""
        error = TargetValidationError(
            {
                "t_a": _schema_error(["a", "b", "c", "a"]),
                "t_b": _schema_error(["x", "y", "z"]),
            }
        )

        rows = error.to_list(max_errors=2)

        assert [(r["target"], r["failure_case"], r["count"]) for r in rows] == [
            ("t_a", "a", 2),
            ("t_a", "b", 1),
            ("t_b", "x", 1),
            ("t_b", "y", 1),
        ]

    def test_to_pandas_matches_to_list_with_max_errors(self, error):
        """`to_pandas(max_errors)` holds the rows of `to_list(max_errors)`."""
        pd.testing.assert_frame_equal(
            error.to_pandas(max_errors=1),
            pd.DataFrame(error.to_list(max_errors=1)),
        )

    def test_exported_from_both_paths(self):
        from crosscontract.submission import (
            TargetValidationError as FromSubmission,
        )

        assert FromSubmission is TargetValidationError


class TestUnclaimedRowsError:
    @pytest.fixture
    def unclaimed_rows(self) -> pd.DataFrame:
        return pd.DataFrame({"id": [1, 2, 3]})

    @pytest.fixture
    def error(self, unclaimed_rows):
        return UnclaimedRowsError(unclaimed_rows)

    def test_unclaimed_rows_are_exposed_unchanged(self, error, unclaimed_rows):
        assert error.unclaimed_rows.equals(unclaimed_rows)

    def test_message_mentions_number_of_unclaimed_rows(self, error):
        assert "3 unclaimed rows found" in str(error)

    def test_to_list_returns_list_of_dicts(self, error, unclaimed_rows):
        rows = error.to_list()
        assert isinstance(rows, list)
        assert all(isinstance(row, dict) for row in rows)
        assert rows == unclaimed_rows.to_dict(orient="records")

    def test_to_pandas_returns_dataframe(self, error, unclaimed_rows):
        df = error.to_pandas()
        pd.testing.assert_frame_equal(df, unclaimed_rows)
