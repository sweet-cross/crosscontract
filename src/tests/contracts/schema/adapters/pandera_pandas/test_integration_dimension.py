"""Integration tests: an assembled DimensionSchema meeting a DataFrame.

Ported from
src/tests/contracts/schema/adapters/pandera/test_integration_dimension_schema.py.
The four hierarchy rules are covered as predicates under
validation/checks/test_dimension_checks.py; what these add is the composite going
through the adapter — `IsValidCrossDimension` unpacking into one pandera check per
rule, and lazy validation collecting several of them.

Each frame is built to trip exactly the rule under test, so the reported set is
asserted with `==` rather than a substring match. The exception is
`test_a_missing_parent_trips_three_rules`, which is deliberate.
"""

import pandas as pd
import pandera.pandas as pa
import pytest

from crosscontract.contracts.schema import DimensionSchema
from crosscontract.contracts.schema.adapters.pandera_pandas import PanderaAdapter
from crosscontract.contracts.schema.validation.checks.dimension_checks import (
    EachLevelHasOther,
    NonRootElementHasParent,
    ParentHasCorrectLevel,
    RootElementHasNoParent,
)

# the label PanderaAdapter._derive_checks gives the hierarchy check, and which
# IsValidCrossDimension passes down to each of its four rules
LABEL = "dimension hierarchy"

ROOT_HAS_PARENT = RootElementHasNoParent(label=LABEL).failure_message()
MISSING_PARENT = NonRootElementHasParent(label=LABEL).failure_message()
WRONG_PARENT_LEVEL = ParentHasCorrectLevel(label=LABEL).failure_message()
MISSING_OTHER = EachLevelHasOther(label=LABEL).failure_message()


@pytest.fixture
def dimension_schema() -> pa.DataFrameSchema:
    return PanderaAdapter.convert_schema(DimensionSchema.model_validate({}))


def _make_df(rows: list[dict]) -> pd.DataFrame:
    """Build a dimension frame from row dicts, filling the columns a test does
    not care about."""
    defaults = {
        "id": "x",
        "level": 0,
        "parent_id": pd.NA,
        "label": "a label",
        "description": "a description",
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


def _reported(exc_info) -> set[str]:
    """The rules a lazy validation reported, as their failure messages.

    Pandera puts exactly one identifying string per check into `failure_cases`,
    which is the `error` the check was built with.
    """
    return set(exc_info.value.failure_cases["check"].astype(str))


VALID_TWO_LEVEL = _make_df(
    [
        {"id": "europe", "level": 0},
        {"id": "other", "level": 0},
        {"id": "germany", "level": 1, "parent_id": "europe"},
        {"id": "europe_other", "level": 1, "parent_id": "europe"},
        {"id": "other_other", "level": 1, "parent_id": "other"},
    ]
)


class TestValidDimension:
    def test_valid_two_level_hierarchy_passes(self, dimension_schema):
        result = dimension_schema.validate(VALID_TWO_LEVEL, lazy=True)
        assert len(result) == len(VALID_TWO_LEVEL)

    def test_valid_three_level_hierarchy_passes(self, dimension_schema):
        """The rules hold at every depth, including under a catch-all."""
        df = _make_df(
            [
                {"id": "world", "level": 0},
                {"id": "other", "level": 0},
                {"id": "europe", "level": 1, "parent_id": "world"},
                {"id": "world_other", "level": 1, "parent_id": "world"},
                {"id": "other_other", "level": 1, "parent_id": "other"},
                {"id": "germany", "level": 2, "parent_id": "europe"},
                {"id": "europe_other", "level": 2, "parent_id": "europe"},
                {"id": "world_other_other", "level": 2, "parent_id": "world_other"},
                {"id": "other_other_other", "level": 2, "parent_id": "other_other"},
            ]
        )
        result = dimension_schema.validate(df, lazy=True)
        assert len(result) == len(df)


class TestOneRuleAtATime:
    """Each defect surfaces as its own rule, because IsValidCrossDimension
    unpacks into one pandera check per rule rather than one opaque failure."""

    def test_root_with_a_parent(self, dimension_schema):
        df = VALID_TWO_LEVEL.copy()
        df.loc[df["id"] == "europe", "parent_id"] = "someone"
        with pytest.raises(pa.errors.SchemaErrors) as exc_info:
            dimension_schema.validate(df, lazy=True)
        assert _reported(exc_info) == {ROOT_HAS_PARENT}

    def test_parent_at_the_wrong_level(self, dimension_schema):
        """`germany` sits at level 2 but names a level 0 parent. The catch-all
        rule is unaffected: it groups by parent, and the group under `world`
        already holds `world_other`."""
        df = _make_df(
            [
                {"id": "world", "level": 0},
                {"id": "other", "level": 0},
                {"id": "europe", "level": 1, "parent_id": "world"},
                {"id": "world_other", "level": 1, "parent_id": "world"},
                {"id": "other_other", "level": 1, "parent_id": "other"},
                {"id": "germany", "level": 2, "parent_id": "world"},
            ]
        )
        with pytest.raises(pa.errors.SchemaErrors) as exc_info:
            dimension_schema.validate(df, lazy=True)
        assert _reported(exc_info) == {WRONG_PARENT_LEVEL}

    def test_missing_root_other(self, dimension_schema):
        """The root group has no `other`, so both of its members fail."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "asia", "level": 0},
                {"id": "child", "level": 1, "parent_id": "europe"},
                {"id": "europe_other", "level": 1, "parent_id": "europe"},
            ]
        )
        with pytest.raises(pa.errors.SchemaErrors) as exc_info:
            dimension_schema.validate(df, lazy=True)
        assert _reported(exc_info) == {MISSING_OTHER}

    def test_missing_child_other(self, dimension_schema):
        """`europe` has children but no `europe_other`, so every child fails."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "other", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "france", "level": 1, "parent_id": "europe"},
                {"id": "other_other", "level": 1, "parent_id": "other"},
            ]
        )
        with pytest.raises(pa.errors.SchemaErrors) as exc_info:
            dimension_schema.validate(df, lazy=True)
        assert _reported(exc_info) == {MISSING_OTHER}

    def test_catch_all_under_the_wrong_name(self, dimension_schema):
        """`other_europe` is the retired naming; the rule wants
        `europe_other`."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "other", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "other_europe", "level": 1, "parent_id": "europe"},
                {"id": "other_other", "level": 1, "parent_id": "other"},
            ]
        )
        with pytest.raises(pa.errors.SchemaErrors) as exc_info:
            dimension_schema.validate(df, lazy=True)
        assert _reported(exc_info) == {MISSING_OTHER}


class TestLazyCollectsSeveralRules:
    def test_a_missing_parent_trips_three_rules(self, dimension_schema):
        """One defect, three reports — the case ADR 0006 records as accepted
        rather than designed. `NonRootElementHasParent` owns it;
        `ParentHasCorrectLevel` fails because a null parent resolves to no level,
        and `EachLevelHasOther` fails because the grouping drops the null key and
        returns no answer for the row.

        This is also what shows lazy validation collecting several hierarchy
        rules rather than stopping at the first.
        """
        df = VALID_TWO_LEVEL.copy()
        df.loc[df["id"] == "germany", "parent_id"] = pd.NA
        with pytest.raises(pa.errors.SchemaErrors) as exc_info:
            dimension_schema.validate(df, lazy=True)
        assert _reported(exc_info) == {
            MISSING_PARENT,
            WRONG_PARENT_LEVEL,
            MISSING_OTHER,
        }
