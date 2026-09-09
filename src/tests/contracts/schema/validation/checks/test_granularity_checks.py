import pandas as pd
import pytest

from crosscontract.contracts.schema.validation.checks import (
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
