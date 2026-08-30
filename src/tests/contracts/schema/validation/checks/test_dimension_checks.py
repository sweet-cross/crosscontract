import pandas as pd
import pytest

from crosscontract.contracts.schema.validation.checks import IsValidCrossDimension
from crosscontract.contracts.schema.validation.checks.dimension_checks import (
    EachLevelHasOther,
    NonRootElementHasParent,
    ParentHasCorrectLevel,
    RootElementHasNoParent,
)

# These port the cases from
# src/tests/contracts/schema/adapters/pandera/test_dimension_check.py, which
# covered the same rules as module-level functions. Only the construction is
# re-pointed. Only IsValidCrossDimension is exported from the package; the four
# rules it is made of are imported from their module.

LABEL = "dimension"


def _make_df(rows: list[dict]) -> pd.DataFrame:
    """Helper to build a dimension DataFrame from row dicts.
    Fills in optional columns with defaults so tests only specify what matters."""
    defaults = {
        "id": "x",
        "level": 0,
        "parent_id": pd.NA,
        "label": pd.NA,
        "description": pd.NA,
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


# ---------------------------------------------------------------------------
# NonRootElementHasParent  (level > 0 → must have parent_id)
# ---------------------------------------------------------------------------
class TestNonRootElementHasParent:
    @pytest.fixture
    def check(self) -> NonRootElementHasParent:
        return NonRootElementHasParent(label=LABEL)

    def test_root_without_parent_passes(self, check: NonRootElementHasParent):
        """The root level is not this rule's business."""
        df = _make_df([{"id": "a", "level": 0}])
        assert check(df).all()

    def test_child_with_parent_passes(self, check: NonRootElementHasParent):
        """A named parent satisfies the rule."""
        df = _make_df([{"id": "a", "level": 1, "parent_id": "root"}])
        assert check(df).all()

    def test_child_without_parent_fails(self, check: NonRootElementHasParent):
        """An entry below the root with no parent is detached from the
        hierarchy."""
        df = _make_df([{"id": "a", "level": 1}])
        assert not check(df).iloc[0]

    def test_child_with_empty_string_parent_fails(self, check: NonRootElementHasParent):
        """An empty string is no parent, the same as a null."""
        df = _make_df([{"id": "a", "level": 2, "parent_id": ""}])
        assert not check(df).iloc[0]

    def test_mixed_rows(self, check: NonRootElementHasParent):
        """Each row is judged on its own."""
        df = _make_df(
            [
                {"id": "root", "level": 0},
                {"id": "ok", "level": 1, "parent_id": "root"},
                {"id": "bad", "level": 1},
            ]
        )
        assert check(df).tolist() == [True, True, False]


# ---------------------------------------------------------------------------
# RootElementHasNoParent  (level 0 → must not have parent_id)
# ---------------------------------------------------------------------------
class TestRootElementHasNoParent:
    @pytest.fixture
    def check(self) -> RootElementHasNoParent:
        return RootElementHasNoParent(label=LABEL)

    def test_root_without_parent_passes(self, check: RootElementHasNoParent):
        """Nothing sits above the root, so it names nothing."""
        df = _make_df([{"id": "a", "level": 0}])
        assert check(df).all()

    def test_root_with_parent_fails(self, check: RootElementHasNoParent):
        """A root entry pointing at anything breaks the top of the hierarchy."""
        df = _make_df([{"id": "a", "level": 0, "parent_id": "someone"}])
        assert not check(df).iloc[0]

    def test_root_with_empty_string_parent_passes(self, check: RootElementHasNoParent):
        """An empty string is no parent, the same as a null."""
        df = _make_df([{"id": "a", "level": 0, "parent_id": ""}])
        assert check(df).all()

    def test_child_with_parent_passes(self, check: RootElementHasNoParent):
        """Entries below the root are not this rule's business."""
        df = _make_df([{"id": "a", "level": 1, "parent_id": "root"}])
        assert check(df).all()

    def test_child_without_parent_passes(self, check: RootElementHasNoParent):
        """Not this check's responsibility — NonRootElementHasParent covers it."""
        df = _make_df([{"id": "a", "level": 2}])
        assert check(df).all()

    def test_mixed_rows(self, check: RootElementHasNoParent):
        """Each row is judged on its own."""
        df = _make_df(
            [
                {"id": "ok_root", "level": 0},
                {"id": "bad_root", "level": 0, "parent_id": "x"},
                {"id": "child", "level": 1, "parent_id": "ok_root"},
            ]
        )
        assert check(df).tolist() == [True, False, True]


# ---------------------------------------------------------------------------
# EachLevelHasOther
#   - level 0: must contain id == "other"
#   - level > 0: each parent must have a child with id == "<parent_id>_other"
# ---------------------------------------------------------------------------
class TestEachLevelHasOther:
    @pytest.fixture
    def check(self) -> EachLevelHasOther:
        return EachLevelHasOther(label=LABEL)

    # --- Valid hierarchies ---

    def test_minimal_valid_hierarchy(self, check: EachLevelHasOther):
        """Single root level with just an 'other' entry."""
        df = _make_df([{"id": "other", "level": 0}])
        assert check(df).all()

    def test_two_level_valid_hierarchy(self, check: EachLevelHasOther):
        """Every parent carries its own catch-all child."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "other", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "europe_other", "level": 1, "parent_id": "europe"},
                {"id": "france", "level": 1, "parent_id": "other"},
                {"id": "other_other", "level": 1, "parent_id": "other"},
            ]
        )
        assert check(df).all()

    def test_three_level_valid_hierarchy(self, check: EachLevelHasOther):
        """The rule applies at every depth, including under a catch-all."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "other", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "europe_other", "level": 1, "parent_id": "europe"},
                {"id": "berlin", "level": 2, "parent_id": "germany"},
                {"id": "germany_other", "level": 2, "parent_id": "germany"},
                {"id": "europe_other_other", "level": 2, "parent_id": "europe_other"},
            ]
        )
        assert check(df).all()

    # --- Missing root "other" ---

    def test_missing_root_other_flags_all_root_rows(self, check: EachLevelHasOther):
        """The catch-all is missing from the root group, so the whole group
        fails."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "asia", "level": 0},
            ]
        )
        assert check(df).tolist() == [False, False]

    def test_missing_root_other_does_not_affect_children(
        self, check: EachLevelHasOther
    ):
        """A group is judged against its own catch-all, not its parent's."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "child", "level": 1, "parent_id": "europe"},
                {"id": "europe_other", "level": 1, "parent_id": "europe"},
            ]
        )
        assert check(df).tolist() == [False, True, True]

    def test_a_row_without_a_parent_is_not_this_rules_business(
        self, check: EachLevelHasOther
    ):
        """With no non-root row naming a parent there is no grouping at all, so
        the answer is empty and every row keeps its initial pass. This is the only
        shape in which a parentless row passes: alongside rows that do name a
        parent it fails here too. NonRootElementHasParent owns that failure and
        reports it either way."""
        df = _make_df(
            [
                {"id": "other", "level": 0},
                {"id": "germany", "level": 1},
            ]
        )
        assert check(df).tolist() == [True, True]

    # --- Missing child "<parent_id>_other" ---

    def test_missing_child_other_flags_siblings(self, check: EachLevelHasOther):
        """Every child under the parent that lacks a catch-all fails."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "other", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "france", "level": 1, "parent_id": "europe"},
                # missing: europe_other
            ]
        )
        assert check(df).tolist() == [True, True, False, False]

    def test_wrong_other_name_fails(self, check: EachLevelHasOther):
        """other_<wrong_parent> present but <correct_parent>_other missing."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "other", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "other_asia", "level": 1, "parent_id": "europe"},
            ]
        )
        result = check(df)
        # children under "europe" fail — other_asia doesn't count
        assert not result.iloc[2]
        assert not result.iloc[3]

    def test_one_parent_valid_another_invalid(self, check: EachLevelHasOther):
        """Groups are judged independently of one another."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "asia", "level": 0},
                {"id": "other", "level": 0},
                # europe children: has europe_other
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "europe_other", "level": 1, "parent_id": "europe"},
                # asia children: missing asia_other
                {"id": "japan", "level": 1, "parent_id": "asia"},
            ]
        )
        result = check(df)
        assert result.iloc[3]  # germany passes
        assert result.iloc[4]  # europe_other passes
        assert not result.iloc[5]  # japan fails (no asia_other)


# ---------------------------------------------------------------------------
# ParentHasCorrectLevel  (level N > 0 → parent must be at level N-1)
# ---------------------------------------------------------------------------
class TestParentHasCorrectLevel:
    @pytest.fixture
    def check(self) -> ParentHasCorrectLevel:
        return ParentHasCorrectLevel(label=LABEL)

    def test_root_rows_always_pass(self, check: ParentHasCorrectLevel):
        """The root has no parent to place."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "other", "level": 0},
            ]
        )
        assert check(df).all()

    def test_valid_two_level_hierarchy(self, check: ParentHasCorrectLevel):
        """A child one level below its parent passes."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
            ]
        )
        assert check(df).all()

    def test_valid_three_level_hierarchy(self, check: ParentHasCorrectLevel):
        """The rule holds at every depth."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "berlin", "level": 2, "parent_id": "germany"},
            ]
        )
        assert check(df).all()

    def test_child_pointing_to_same_level_fails(self, check: ParentHasCorrectLevel):
        """A sideways parent is not one level above."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "france", "level": 1, "parent_id": "germany"},
            ]
        )
        assert check(df).tolist() == [True, True, False]

    def test_child_pointing_to_grandparent_fails(self, check: ParentHasCorrectLevel):
        """Skipping a level leaves a gap in the hierarchy."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "berlin", "level": 2, "parent_id": "europe"},
            ]
        )
        assert check(df).tolist() == [True, True, False]

    def test_child_pointing_to_deeper_level_fails(self, check: ParentHasCorrectLevel):
        """A parent below the child inverts the hierarchy."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "berlin", "level": 2, "parent_id": "germany"},
                {"id": "bad", "level": 1, "parent_id": "berlin"},
            ]
        )
        assert not check(df).iloc[3]

    def test_dangling_parent_id_fails(self, check: ParentHasCorrectLevel):
        """parent_id references a non-existent id — the lookup produces NA,
        which counts as a failure rather than passing."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "ghost_child", "level": 1, "parent_id": "nonexistent"},
            ]
        )
        assert check(df).tolist() == [True, False]

    def test_dangling_parent_id_fails_with_nullable_level_dtype(
        self, check: ParentHasCorrectLevel
    ):
        """The adapter coerces an integer field to nullable 'Int64', where a
        comparison against NA yields NA rather than False. The NA must still be
        read as a failure."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "ghost_child", "level": 1, "parent_id": "nonexistent"},
            ]
        ).astype({"level": "Int64"})
        assert check(df).tolist() == [True, False]

    def test_mixed_valid_and_invalid(self, check: ParentHasCorrectLevel):
        """Each row is judged on its own."""
        df = _make_df(
            [
                {"id": "world", "level": 0},
                {"id": "europe", "level": 1, "parent_id": "world"},
                {"id": "germany", "level": 2, "parent_id": "europe"},
                {"id": "bad_skip", "level": 2, "parent_id": "world"},
                {"id": "bad_same", "level": 1, "parent_id": "europe"},
            ]
        )
        assert check(df).tolist() == [True, True, True, False, False]


# ---------------------------------------------------------------------------
# IsValidCrossDimension  (the four rules taken together)
# ---------------------------------------------------------------------------
class TestIsValidCrossDimension:
    @pytest.fixture
    def check(self) -> IsValidCrossDimension:
        return IsValidCrossDimension(label=LABEL)

    def test_valid_hierarchy_passes(self, check: IsValidCrossDimension):
        """A hierarchy satisfying all four rules passes on every row."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "other", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "europe_other", "level": 1, "parent_id": "europe"},
                {"id": "other_other", "level": 1, "parent_id": "other"},
            ]
        )
        assert check(df).all()

    def test_a_root_with_a_parent_fails(self, check: IsValidCrossDimension):
        """Rule 1 breaking is enough to fail the row."""
        df = _make_df(
            [
                {"id": "other", "level": 0},
                {"id": "europe", "level": 0, "parent_id": "other"},
            ]
        )
        assert not check(df).iloc[1]

    def test_a_child_without_a_parent_fails(self, check: IsValidCrossDimension):
        """Rule 2 breaking is enough to fail the row."""
        df = _make_df(
            [
                {"id": "other", "level": 0},
                {"id": "germany", "level": 1},
            ]
        )
        assert not check(df).iloc[1]

    def test_a_child_skipping_a_level_fails(self, check: IsValidCrossDimension):
        """Rule 3 breaking is enough to fail the row."""
        df = _make_df(
            [
                {"id": "other", "level": 0},
                {"id": "berlin", "level": 2, "parent_id": "other"},
            ]
        )
        assert not check(df).iloc[1]

    def test_a_missing_catch_all_fails(self, check: IsValidCrossDimension):
        """Rule 4 breaking is enough to fail the row."""
        df = _make_df([{"id": "europe", "level": 0}])
        assert not check(df).iloc[0]

    def test_to_pandera_unpacks_into_one_check_per_rule(
        self, check: IsValidCrossDimension
    ):
        """The composite reports its four rules separately rather than as one
        opaque failure."""
        assert len(check.to_pandera()) == 4

    def test_to_pandera_carries_the_rule_failure_messages(
        self, check: IsValidCrossDimension
    ):
        """Each pandera check is identified by the message of the rule it
        enforces, not by the composite's."""
        errors = [c.error for c in check.to_pandera()]
        assert RootElementHasNoParent(label=LABEL).failure_message() in errors
        assert NonRootElementHasParent(label=LABEL).failure_message() in errors
        assert EachLevelHasOther(label=LABEL).failure_message() in errors
        assert ParentHasCorrectLevel(label=LABEL).failure_message() in errors

    def test_column_names_are_configurable(self):
        """A frame that spells the hierarchy columns differently validates the
        same way, and the configured names reach every rule."""
        check = IsValidCrossDimension(
            label=LABEL, id_col="key", parent_id_col="parent", level_col="depth"
        )
        df = pd.DataFrame(
            [
                {"key": "other", "depth": 0, "parent": pd.NA},
                {"key": "europe", "depth": 0, "parent": pd.NA},
                {"key": "europe_other", "depth": 1, "parent": "europe"},
            ]
        )
        assert check(df).all()
