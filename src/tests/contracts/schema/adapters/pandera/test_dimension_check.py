import pandas as pd

from crosscontract.contracts.schema.adapters._pandera_dimension_checks import (
    _check_other_entries,
    _check_parent_id_required,
    _check_parent_level,
    _check_root_no_parent,
)


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
# _check_parent_id_required  (level > 0 → must have parent_id)
# ---------------------------------------------------------------------------
class TestCheckParentIdRequired:
    def test_root_without_parent_passes(self):
        df = _make_df([{"id": "a", "level": 0}])
        assert _check_parent_id_required(df).all()

    def test_child_with_parent_passes(self):
        df = _make_df([{"id": "a", "level": 1, "parent_id": "root"}])
        assert _check_parent_id_required(df).all()

    def test_child_without_parent_fails(self):
        df = _make_df([{"id": "a", "level": 1}])
        result = _check_parent_id_required(df)
        assert not result.iloc[0]

    def test_child_with_empty_string_parent_fails(self):
        df = _make_df([{"id": "a", "level": 2, "parent_id": ""}])
        result = _check_parent_id_required(df)
        assert not result.iloc[0]

    def test_mixed_rows(self):
        df = _make_df(
            [
                {"id": "root", "level": 0},
                {"id": "ok", "level": 1, "parent_id": "root"},
                {"id": "bad", "level": 1},
            ]
        )
        result = _check_parent_id_required(df)
        assert result.iloc[0]  # root passes
        assert result.iloc[1]  # child with parent passes
        assert not result.iloc[2]  # child without parent fails


# ---------------------------------------------------------------------------
# _check_root_no_parent  (level 0 → must not have parent_id)
# ---------------------------------------------------------------------------
class TestCheckRootNoParent:
    def test_root_without_parent_passes(self):
        df = _make_df([{"id": "a", "level": 0}])
        assert _check_root_no_parent(df).all()

    def test_root_with_parent_fails(self):
        df = _make_df([{"id": "a", "level": 0, "parent_id": "someone"}])
        result = _check_root_no_parent(df)
        assert not result.iloc[0]

    def test_root_with_empty_string_parent_passes(self):
        df = _make_df([{"id": "a", "level": 0, "parent_id": ""}])
        assert _check_root_no_parent(df).all()

    def test_child_with_parent_passes(self):
        df = _make_df([{"id": "a", "level": 1, "parent_id": "root"}])
        assert _check_root_no_parent(df).all()

    def test_child_without_parent_passes(self):
        """Not this check's responsibility — _check_parent_id_required covers it."""
        df = _make_df([{"id": "a", "level": 2}])
        assert _check_root_no_parent(df).all()

    def test_mixed_rows(self):
        df = _make_df(
            [
                {"id": "ok_root", "level": 0},
                {"id": "bad_root", "level": 0, "parent_id": "x"},
                {"id": "child", "level": 1, "parent_id": "ok_root"},
            ]
        )
        result = _check_root_no_parent(df)
        assert result.iloc[0]  # root without parent passes
        assert not result.iloc[1]  # root with parent fails
        assert result.iloc[2]  # child is irrelevant, passes


# ---------------------------------------------------------------------------
# _check_other_entries
#   - level 0: must contain id == "other"
#   - level > 0: each parent must have a child with id == "other_<parent_id>"
# ---------------------------------------------------------------------------
class TestCheckOtherEntries:
    # --- Valid hierarchies ---

    def test_minimal_valid_hierarchy(self):
        """Single root level with just an 'other' entry."""
        df = _make_df([{"id": "other", "level": 0}])
        assert _check_other_entries(df).all()

    def test_two_level_valid_hierarchy(self):
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "other", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "other_europe", "level": 1, "parent_id": "europe"},
                {"id": "france", "level": 1, "parent_id": "other"},
                {"id": "other_other", "level": 1, "parent_id": "other"},
            ]
        )
        assert _check_other_entries(df).all()

    def test_three_level_valid_hierarchy(self):
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "other", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "other_europe", "level": 1, "parent_id": "europe"},
                {"id": "berlin", "level": 2, "parent_id": "germany"},
                {"id": "other_germany", "level": 2, "parent_id": "germany"},
                {"id": "other_other_europe", "level": 2, "parent_id": "other_europe"},
            ]
        )
        assert _check_other_entries(df).all()

    # --- Missing root "other" ---

    def test_missing_root_other_flags_all_root_rows(self):
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "asia", "level": 0},
            ]
        )
        result = _check_other_entries(df)
        assert not result.iloc[0]
        assert not result.iloc[1]

    def test_missing_root_other_does_not_affect_children(self):
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "child", "level": 1, "parent_id": "europe"},
                {"id": "other_europe", "level": 1, "parent_id": "europe"},
            ]
        )
        result = _check_other_entries(df)
        # root rows fail
        assert not result.iloc[0]
        # children are fine (their parent has other_europe)
        assert result.iloc[1]
        assert result.iloc[2]

    # --- Missing child "other_<parent_id>" ---

    def test_missing_child_other_flags_siblings(self):
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "other", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "france", "level": 1, "parent_id": "europe"},
                # missing: other_europe
            ]
        )
        result = _check_other_entries(df)
        # root is fine
        assert result.iloc[0]
        assert result.iloc[1]
        # all children under "europe" fail
        assert not result.iloc[2]
        assert not result.iloc[3]

    def test_wrong_other_name_fails(self):
        """other_<wrong_parent> present but other_<correct_parent> missing."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "other", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "other_asia", "level": 1, "parent_id": "europe"},
            ]
        )
        result = _check_other_entries(df)
        # children under "europe" fail — other_asia doesn't count
        assert not result.iloc[2]
        assert not result.iloc[3]

    def test_one_parent_valid_another_invalid(self):
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "asia", "level": 0},
                {"id": "other", "level": 0},
                # europe children: has other_europe ✓
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "other_europe", "level": 1, "parent_id": "europe"},
                # asia children: missing other_asia ✗
                {"id": "japan", "level": 1, "parent_id": "asia"},
            ]
        )
        result = _check_other_entries(df)
        assert result.iloc[3]  # germany passes
        assert result.iloc[4]  # other_europe passes
        assert not result.iloc[5]  # japan fails (no other_asia)


# ---------------------------------------------------------------------------
# _check_parent_level  (level N > 0 → parent must be at level N-1)
# ---------------------------------------------------------------------------
class TestCheckParentLevel:
    def test_root_rows_always_pass(self):
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "other", "level": 0},
            ]
        )
        assert _check_parent_level(df).all()

    def test_valid_two_level_hierarchy(self):
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
            ]
        )
        assert _check_parent_level(df).all()

    def test_valid_three_level_hierarchy(self):
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "berlin", "level": 2, "parent_id": "germany"},
            ]
        )
        assert _check_parent_level(df).all()

    def test_child_pointing_to_same_level_fails(self):
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "france", "level": 1, "parent_id": "germany"},
            ]
        )
        result = _check_parent_level(df)
        assert result.iloc[0]  # root passes
        assert result.iloc[1]  # germany → europe (0→1) passes
        assert not result.iloc[2]  # france → germany (1→1) fails

    def test_child_pointing_to_grandparent_fails(self):
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "berlin", "level": 2, "parent_id": "europe"},
            ]
        )
        result = _check_parent_level(df)
        assert result.iloc[0]  # root passes
        assert result.iloc[1]  # germany → europe (0→1) passes
        assert not result.iloc[2]  # berlin → europe (0→2) fails — skips a level

    def test_child_pointing_to_deeper_level_fails(self):
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "berlin", "level": 2, "parent_id": "germany"},
                {"id": "bad", "level": 1, "parent_id": "berlin"},
            ]
        )
        result = _check_parent_level(df)
        assert not result.iloc[3]  # level 1 pointing at level 2 fails

    def test_dangling_parent_id_fails(self):
        """parent_id references a non-existent id — map produces NaN, fails equality."""
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "ghost_child", "level": 1, "parent_id": "nonexistent"},
            ]
        )
        result = _check_parent_level(df)
        assert result.iloc[0]
        assert not result.iloc[1]

    def test_mixed_valid_and_invalid(self):
        df = _make_df(
            [
                {"id": "world", "level": 0},
                {"id": "europe", "level": 1, "parent_id": "world"},
                {"id": "germany", "level": 2, "parent_id": "europe"},
                {"id": "bad_skip", "level": 2, "parent_id": "world"},
                {"id": "bad_same", "level": 1, "parent_id": "europe"},
            ]
        )
        result = _check_parent_level(df)
        assert result.iloc[0]  # root
        assert result.iloc[1]  # europe → world (0→1) ✓
        assert result.iloc[2]  # germany → europe (1→2) ✓
        assert not result.iloc[3]  # bad_skip → world (0→2) ✗
        assert not result.iloc[4]  # bad_same → europe (1→1) ✗
