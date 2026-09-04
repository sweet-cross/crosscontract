import pandas as pd
import pytest
from pydantic import ValidationError

from crosscontract.contracts.schema.validation.checks import (
    IsIn,
    IsNotIn,
    IsNotNull,
    IsSubsetOf,
    IsUnique,
)

# Each check is called directly, so these tests cover the row-level predicate
# only. The conversion into pandera checks lives on BaseCheck and is covered in
# test_abstract_base.py.


# ---------------------------------------------------------------------------
# IsUnique  (the given columns hold jointly unique values)
# ---------------------------------------------------------------------------
class TestIsUnique:
    def test_unique_values_pass(self):
        """Every row passes when no value repeats."""
        check = IsUnique(label="id", columns=["id"])
        df = pd.DataFrame({"id": ["a", "b", "c"]})
        assert check(df).tolist() == [True, True, True]

    def test_all_occurrences_of_a_duplicate_fail(self):
        """A repeated value fails on every row it appears in, not just the later
        one, so the report points at the whole collision."""
        check = IsUnique(label="id", columns=["id"])
        df = pd.DataFrame({"id": ["a", "a", "b"]})
        assert check(df).tolist() == [False, False, True]

    def test_composite_columns_are_judged_jointly(self):
        """A value repeating in one column is fine as long as the combination
        across all columns stays unique."""
        check = IsUnique(label="key", columns=["x", "y"])
        df = pd.DataFrame({"x": ["a", "a"], "y": [1, 2]})
        assert check(df).tolist() == [True, True]

    def test_composite_columns_fail_when_the_combination_repeats(self):
        """The combination, not the individual column, is what must be unique."""
        check = IsUnique(label="key", columns=["x", "y"])
        df = pd.DataFrame({"x": ["a", "a"], "y": [1, 1]})
        assert check(df).tolist() == [False, False]

    def test_failure_message_names_the_label(self):
        """The message identifies the check by its label."""
        check = IsUnique(label="primary key", columns=["id"])
        assert "primary key" in check.failure_message()


# ---------------------------------------------------------------------------
# IsIn  (the given columns only hold values from the existing ones)
# ---------------------------------------------------------------------------
class TestIsIn:
    def test_values_among_the_existing_ones_pass(self):
        """A row passes when its key appears in the existing values."""
        check = IsIn(label="region", columns=["region"], existing=[("de",), ("fr",)])
        df = pd.DataFrame({"region": ["de", "fr"]})
        assert check(df).tolist() == [True, True]

    def test_values_outside_the_existing_ones_fail(self):
        """A row fails when its key is absent from the existing values."""
        check = IsIn(label="region", columns=["region"], existing=[("de",)])
        df = pd.DataFrame({"region": ["de", "xx"]})
        assert check(df).tolist() == [True, False]

    def test_empty_existing_fails_every_row(self):
        """An empty set of existing values means the referenced table holds no
        rows, so every row legitimately fails."""
        check = IsIn(label="region", columns=["region"], existing=[])
        df = pd.DataFrame({"region": ["de", "fr"]})
        assert check(df).tolist() == [False, False]

    def test_composite_columns_compare_positionally(self):
        """A composite key matches column by column in the declared order, so a
        reversed existing tuple does not match."""
        check = IsIn(label="key", columns=["x", "y"], existing=[("a", 1)])
        df = pd.DataFrame({"x": ["a", 1], "y": [1, "a"]})
        assert check(df).tolist() == [True, False]

    def test_result_keeps_the_frame_index(self):
        """The result is aligned to the frame it was called with, so pandera can
        report which rows failed."""
        check = IsIn(label="region", columns=["region"], existing=[("de",)])
        df = pd.DataFrame({"region": ["de", "xx"]}, index=[10, 11])
        assert check(df).index.tolist() == [10, 11]

    def test_failure_message_names_the_columns(self):
        """The message identifies the columns that were checked."""
        check = IsIn(label="region", columns=["region"], existing=[("de",)])
        assert "region" in check.failure_message()

    def test_existing_values_must_be_as_wide_as_the_columns(self):
        """A two-wide value against a one-column key would match nothing and
        silently fail every row, so it is rejected at construction."""
        with pytest.raises(ValidationError):
            IsIn(label="region", columns=["region"], existing=[("de", 2020)])


# ---------------------------------------------------------------------------
# IsNotIn  (the given columns hold none of the existing values)
# ---------------------------------------------------------------------------
class TestIsNotIn:
    def test_values_outside_the_existing_ones_pass(self):
        """A row passes when its key is absent from the existing values."""
        check = IsNotIn(label="id", columns=["id"], existing=[("a",)])
        df = pd.DataFrame({"id": ["b", "c"]})
        assert check(df).tolist() == [True, True]

    def test_values_among_the_existing_ones_fail(self):
        """A row fails when its key collides with an existing value."""
        check = IsNotIn(label="id", columns=["id"], existing=[("a",)])
        df = pd.DataFrame({"id": ["a", "b"]})
        assert check(df).tolist() == [False, True]

    def test_empty_existing_passes_every_row(self):
        """Nothing to collide with means nothing can fail — the mirror image of
        the empty case in IsIn."""
        check = IsNotIn(label="id", columns=["id"], existing=[])
        df = pd.DataFrame({"id": ["a", "b"]})
        assert check(df).tolist() == [True, True]

    def test_composite_columns_compare_positionally(self):
        """A composite key collides only when it matches column by column in the
        declared order."""
        check = IsNotIn(label="key", columns=["x", "y"], existing=[("a", 1)])
        df = pd.DataFrame({"x": ["a", 1], "y": [1, "a"]})
        assert check(df).tolist() == [False, True]

    def test_result_keeps_the_frame_index(self):
        """The result is aligned to the frame it was called with."""
        check = IsNotIn(label="id", columns=["id"], existing=[("a",)])
        df = pd.DataFrame({"id": ["a", "b"]}, index=[10, 11])
        assert check(df).index.tolist() == [10, 11]

    def test_failure_message_names_the_columns(self):
        """The message identifies the columns that were checked."""
        check = IsNotIn(label="id", columns=["id"], existing=[("a",)])
        assert "id" in check.failure_message()

    def test_existing_values_must_be_as_wide_as_the_columns(self):
        """A two-wide value against a one-column key would collide with nothing
        and silently pass every row, so it is rejected at construction."""
        with pytest.raises(ValidationError):
            IsNotIn(label="id", columns=["id"], existing=[("a", 1)])


# ---------------------------------------------------------------------------
# IsSubsetOf  (a foreign key: non-null values appear among the referenced ones)
# ---------------------------------------------------------------------------
class TestIsSubsetOf:
    def test_referenced_values_pass(self):
        """A row passes when its key appears among the referenced values."""
        check = IsSubsetOf(label="region", columns=["region"], allowed=[("de",)])
        df = pd.DataFrame({"region": ["de", "de"]})
        assert check(df).tolist() == [True, True]

    def test_unreferenced_values_fail(self):
        """A row fails when its key is absent from the referenced values."""
        check = IsSubsetOf(label="region", columns=["region"], allowed=[("de",)])
        df = pd.DataFrame({"region": ["de", "xx"]})
        assert check(df).tolist() == [True, False]

    def test_null_rows_pass(self):
        """SQL treats a null reference as "no relationship" rather than a broken
        one, so it is never a violation."""
        check = IsSubsetOf(label="region", columns=["region"], allowed=[("de",)])
        df = pd.DataFrame({"region": ["de", None]})
        assert check(df).tolist() == [True, True]

    def test_empty_strings_are_read_as_null(self):
        """A tabular source carries no null of its own, so a blank cell means
        the same thing."""
        check = IsSubsetOf(label="region", columns=["region"], allowed=[("de",)])
        df = pd.DataFrame({"region": ["de", ""]})
        assert check(df).tolist() == [True, True]

    def test_one_null_passes_a_composite_row(self):
        """Under MATCH SIMPLE a single null anywhere in the key passes the row,
        even when the remaining columns match nothing."""
        check = IsSubsetOf(label="key", columns=["x", "y"], allowed=[("a", 1)])
        df = pd.DataFrame({"x": ["a", "zzz"], "y": [1, None]})
        assert check(df).tolist() == [True, True]

    def test_composite_columns_compare_positionally(self):
        """A composite key matches column by column in the declared order."""
        check = IsSubsetOf(label="key", columns=["x", "y"], allowed=[("a", 1)])
        df = pd.DataFrame({"x": ["a", 1], "y": [1, "a"]})
        assert check(df).tolist() == [True, False]

    def test_within_validates_against_the_frames_own_rows(self):
        """A self-referencing key needs no supplied values: the frame's own
        rows are the referenced set."""
        check = IsSubsetOf(label="parent", columns=["parent_id"], within=["id"])
        df = pd.DataFrame(
            {"id": ["root", "a", "b"], "parent_id": [None, "root", "nope"]}
        )
        assert check(df).tolist() == [True, True, False]

    def test_within_and_allowed_are_unioned(self):
        """Supplying values for a self-referencing key adds to the frame's own
        rows rather than replacing them."""
        check = IsSubsetOf(
            label="parent",
            columns=["parent_id"],
            allowed=[("stored",)],
            within=["id"],
        )
        df = pd.DataFrame({"id": ["a", "b"], "parent_id": ["a", "stored"]})
        assert check(df).tolist() == [True, True]

    def test_empty_allowed_fails_every_non_null_row(self):
        """No referenced values and no self-reference means the referenced table
        exists and is empty, which every populated row fails and every null row
        survives."""
        check = IsSubsetOf(label="region", columns=["region"])
        df = pd.DataFrame({"region": ["de", None]})
        assert check(df).tolist() == [False, True]

    def test_result_keeps_the_frame_index(self):
        """The result is aligned to the frame it was called with."""
        check = IsSubsetOf(label="region", columns=["region"], allowed=[("de",)])
        df = pd.DataFrame({"region": ["de", "xx"]}, index=[10, 11])
        assert check(df).index.tolist() == [10, 11]

    def test_ignore_na_defaults_to_false(self):
        """The check decides itself that null rows pass, so pandera must not
        drop them first."""
        assert IsSubsetOf(label="region", columns=["region"]).ignore_na is False

    def test_allowed_values_must_be_as_wide_as_the_columns(self):
        """A value of the wrong width would match nothing and silently fail
        every row, so it is rejected at construction."""
        with pytest.raises(ValidationError):
            IsSubsetOf(label="region", columns=["region"], allowed=[("de", 2020)])

    def test_within_must_be_as_wide_as_the_columns(self):
        """The referenced columns build keys of their own width, so a mismatch
        would match nothing either."""
        with pytest.raises(ValidationError):
            IsSubsetOf(label="parent", columns=["parent_id"], within=["id", "level"])

    def test_failure_message_names_the_columns(self):
        """The message identifies the columns that were checked."""
        check = IsSubsetOf(label="region", columns=["region"], allowed=[("de",)])
        assert "region" in check.failure_message()


# ---------------------------------------------------------------------------
# IsNotNull  (the given columns hold no null values)
# ---------------------------------------------------------------------------
class TestIsNotNull:
    def test_populated_rows_pass(self):
        """Every row passes when none of the columns is null."""
        check = IsNotNull(label="id", columns=["id"])
        df = pd.DataFrame({"id": ["a", "b"]})
        assert check(df).tolist() == [True, True]

    def test_null_values_fail(self):
        """A null in the checked column fails that row."""
        check = IsNotNull(label="id", columns=["id"])
        df = pd.DataFrame({"id": ["a", None]})
        assert check(df).tolist() == [True, False]

    def test_a_null_in_any_column_fails_the_row(self):
        """For a composite key, one null anywhere in the row is enough to fail
        it."""
        check = IsNotNull(label="key", columns=["x", "y"])
        df = pd.DataFrame({"x": ["a", "b"], "y": [1, None]})
        assert check(df).tolist() == [True, False]

    def test_empty_strings_are_not_null(self):
        """Only actual nulls fail; an empty string is a value like any other."""
        check = IsNotNull(label="id", columns=["id"])
        df = pd.DataFrame({"id": ["", "a"]})
        assert check(df).tolist() == [True, True]

    def test_ignore_na_defaults_to_false(self):
        """This check inspects the nulls itself, so pandera must not drop the
        null rows before it runs."""
        assert IsNotNull(label="id", columns=["id"]).ignore_na is False

    def test_failure_message_names_the_columns(self):
        """The message identifies the columns that were checked."""
        check = IsNotNull(label="id", columns=["id"])
        assert "id" in check.failure_message()
