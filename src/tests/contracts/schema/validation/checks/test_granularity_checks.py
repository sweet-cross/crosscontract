import pandas as pd
import pytest

from crosscontract.contracts.schema.validation.checks.hierarchy_checks import (
    HasNoDescendantInGroup,
)

# The check is called directly, so these tests cover the row-level predicate
# only. The conversion into pandera checks lives on BaseCheck and is covered in
# test_abstract_base.py.

LABEL = "dimension granularity"

# A three-level region hierarchy: two roots plus the mandatory catch-all, one
# branch split below 'ch', and one split again below 'ch_ag'.
PARENT_MAP = {
    "ch": None,
    "de": None,
    "other": None,
    "ch_ag": "ch",
    "ch_other": "ch",
    "ch_ag_zurich": "ch_ag",
    "ch_ag_other": "ch_ag",
}


def _make_df(rows: list[dict]) -> pd.DataFrame:
    """Helper to build a fact DataFrame from row dicts.
    Fills in the columns the check does not read with defaults so tests only
    specify what matters."""
    defaults = {
        "model": "m1",
        "scenario": "A",
        "year": 2030,
        "region": "ch",
        "value": 1.0,
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


class TestHasNoDescendantInGroup:
    @pytest.fixture
    def check(self) -> HasNoDescendantInGroup:
        return HasNoDescendantInGroup(
            label=LABEL,
            column="region",
            group_columns=["model", "scenario", "year"],
            parent_map=PARENT_MAP,
        )

    def test_aggregate_fails_when_a_descendant_shares_its_group(
        self, check: HasNoDescendantInGroup
    ):
        """Summing the column would count 'ch_ag' twice — once on its own and
        once inside 'ch'. The aggregate row is the one reported, because that is
        the row the submitter has to remove."""
        df = _make_df(
            [
                {"region": "ch", "value": 100.0},
                {"region": "ch_ag", "value": 30.0},
            ]
        )
        assert check(df).tolist() == [False, True]

    def test_aggregate_and_descendant_in_different_groups_pass(
        self, check: HasNoDescendantInGroup
    ):
        """One scenario reporting at 'ch' while another reports at 'ch_ag' is
        legal: each group sums correctly on its own, and rolling both up to the
        root draws on different rows."""
        df = _make_df(
            [
                {"scenario": "A", "region": "ch", "value": 100.0},
                {"scenario": "B", "region": "ch_ag", "value": 30.0},
            ]
        )
        assert check(df).tolist() == [True, True]

    def test_two_models_may_report_at_different_granularities(
        self, check: HasNoDescendantInGroup
    ):
        """Two models are alternative estimates of the same quantity, never
        additive parts of one, so one reporting at 'ch' while the other reports
        at 'ch_ag' under the same scenario is legal and must not be flagged.

        This holds only because 'model' is a group column, which
        `ValueVariableSchema` guarantees: a model column is a string foreign key
        into a dimension, and every non-numeric field is in the primary key.
        Were it to fall out of the group, these two rows would collapse into one
        and be rejected — while their primary keys stay distinct, so no other
        check would report the defect either.
        """
        df = _make_df(
            [
                {"model": "m1", "region": "ch", "value": 100.0},
                {"model": "m2", "region": "ch_ag", "value": 30.0},
            ]
        )
        assert check(df).tolist() == [True, True]

    def test_siblings_pass(self, check: HasNoDescendantInGroup):
        """Puts the two children of 'ch' in one group and expects both to pass.
        Neither is an ancestor of the other, so the two together are exactly
        how a group is meant to report below 'ch'."""
        df = _make_df(
            [
                {"region": "ch_ag", "value": 30.0},
                {"region": "ch_other", "value": 70.0},
            ]
        )
        assert check(df).tolist() == [True, True]

    def test_grandparent_fails_when_the_intermediate_level_is_absent(
        self, check: HasNoDescendantInGroup
    ):
        """Puts 'ch' beside its grandchild 'ch_ag_zurich' with 'ch_ag' missing
        from the frame, and expects the grandparent to fail. The rule follows
        the whole chain of parents, not only the direct one, so skipping a
        level does not escape it."""
        df = _make_df(
            [
                {"region": "ch", "value": 100.0},
                {"region": "ch_ag_zurich", "value": 10.0},
            ]
        )
        assert check(df).tolist() == [False, True]

    def test_parent_fails_beside_its_own_catch_all(
        self, check: HasNoDescendantInGroup
    ):
        """Puts 'ch' beside 'ch_other' and expects 'ch' to fail. A catch-all is
        a child like any other, and this is the shape that occurs in practice:
        a submitter reports the total and then the remainder underneath it."""
        df = _make_df(
            [
                {"region": "ch", "value": 100.0},
                {"region": "ch_other", "value": 70.0},
            ]
        )
        assert check(df).tolist() == [False, True]

    def test_member_absent_from_the_parent_map_passes(
        self, check: HasNoDescendantInGroup
    ):
        """Reports a member the dimension does not contain and expects it to
        pass. It has no ancestors and is nobody's ancestor, so this check has
        nothing to say about it — an unknown member is `IsSubsetOf`'s defect to
        report."""
        df = _make_df(
            [
                {"region": "atlantis", "value": 5.0},
                {"region": "ch", "value": 100.0},
            ]
        )
        assert check(df).tolist() == [True, True]

    def test_null_member_passes_and_leaves_the_other_rows_judged(
        self, check: HasNoDescendantInGroup
    ):
        """Puts a null member in a group that also holds a real violation, and
        expects the null row to pass while 'ch' still fails. A null belongs to
        no branch, so it neither fails nor shields the rows around it.

        The assertion is on the predicate's own return value. `ignore_na` is
        not what makes this pass: on a DataFrame-level check pandera does not
        filter rows before calling the predicate.
        """
        df = _make_df(
            [
                {"region": None, "value": 5.0},
                {"region": "ch", "value": 100.0},
                {"region": "ch_ag", "value": 30.0},
            ]
        )
        assert check(df).tolist() == [True, False, True]

    def test_rows_null_in_a_group_column_share_a_group(
        self, check: HasNoDescendantInGroup
    ):
        """Gives two rows the same null year and expects them to be compared
        as one group, so 'ch' fails because 'ch_ag' is there.

        The null is a float NaN in a numeric column, which is the case that
        breaks: a NaN inside a group key equals no other NaN, so without the
        normalisation in `_row_keys` these two rows would form separate groups
        and the violation would go unreported.
        """
        df = _make_df(
            [
                {"year": float("nan"), "region": "ch", "value": 100.0},
                {"year": float("nan"), "region": "ch_ag", "value": 30.0},
            ]
        )
        assert check(df).tolist() == [False, True]

    def test_empty_string_parent_ends_the_chain(self):
        """Asks for the ancestors of a member whose parent is an empty string
        and expects none. A blank cell is how a tabular source spells "no
        parent", so it must terminate a chain exactly as a null does rather
        than be walked as a member id of its own.

        This inspects `_ancestors` because the difference is invisible from the
        predicate: a phantom '' ancestor would only change a verdict for a row
        whose member is itself ''.
        """
        check = HasNoDescendantInGroup(
            label=LABEL,
            column="region",
            group_columns=["model", "scenario", "year"],
            parent_map={"ch": "", "ch_ag": "ch"},
        )
        assert check._ancestors(pd.Series(["ch", "ch_ag"])) == {
            "ch": [],
            "ch_ag": ["ch"],
        }

    def test_cyclic_parent_map_terminates(self):
        """Runs the check against a parent map that loops back on itself and
        expects it to return rather than walk forever. A resolver can hand over
        any frame, and a hanging upload is a worse failure than a wrong one.

        Only termination and the shape of the result are asserted. Which rows a
        malformed hierarchy marks is not a meaningful answer.
        """
        check = HasNoDescendantInGroup(
            label=LABEL,
            column="region",
            group_columns=["model", "scenario", "year"],
            parent_map={"a": "b", "b": "a"},
        )
        df = _make_df([{"region": "a"}, {"region": "b"}])
        result = check(df)
        assert len(result) == 2
        assert result.dtype == bool

    def test_empty_dataframe_passes(self, check: HasNoDescendantInGroup):
        """Runs the check over a frame with the right columns and no rows, and
        expects an empty result rather than an error. There is nothing to
        double-count in no data."""
        df = pd.DataFrame(columns=["model", "scenario", "year", "region", "value"])
        assert check(df).tolist() == []

    def test_single_row_passes(self, check: HasNoDescendantInGroup):
        """Puts one row in a group on its own and expects it to pass. The rule
        is about a member sitting above another member, so it takes two rows to
        break it."""
        df = _make_df([{"region": "ch", "value": 100.0}])
        assert check(df).tolist() == [True]

    def test_duplicate_rows_pass(self, check: HasNoDescendantInGroup):
        """Repeats the same member twice in one group and expects both rows to
        pass. A member does not sit above itself, so there is no double-counting
        of the kind this rule is about. The repetition is a duplicate primary
        key, which `IsUnique` reports."""
        df = _make_df(
            [
                {"region": "ch", "value": 100.0},
                {"region": "ch", "value": 100.0},
            ]
        )
        assert check(df).tolist() == [True, True]

    def test_a_group_is_shared_only_when_every_group_column_matches(
        self, check: HasNoDescendantInGroup
    ):
        """Reports 'ch' and 'ch_ag' twice over: once with the two rows differing
        in a single group column, and once with all three matching. Expects the
        first pair to pass and the second to fail, which is what makes the group
        the whole key rather than any one column of it."""
        differing_year = _make_df(
            [
                {"year": 2030, "region": "ch", "value": 100.0},
                {"year": 2040, "region": "ch_ag", "value": 30.0},
            ]
        )
        assert check(differing_year).tolist() == [True, True]

        same_group = _make_df(
            [
                {"year": 2030, "region": "ch", "value": 100.0},
                {"year": 2030, "region": "ch_ag", "value": 30.0},
            ]
        )
        assert check(same_group).tolist() == [False, True]

    def test_to_pandera_returns_one_check_carrying_the_failure_message(
        self, check: HasNoDescendantInGroup
    ):
        """Expects a single pandera check identified by `failure_message()`.
        One rule with one remedy is reported as one failure, unlike
        `IsValidCrossDimension`, which unpacks into a check per sub-rule so a
        report can name which of them broke."""
        pandera_checks = check.to_pandera()
        assert len(pandera_checks) == 1
        assert pandera_checks[0].error == check.failure_message()
