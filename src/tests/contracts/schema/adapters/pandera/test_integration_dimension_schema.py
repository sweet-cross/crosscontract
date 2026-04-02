"""Integration tests for PanderaPandasAdapter with DimensionSchema validation."""

import pandas as pd
import pandera.pandas as pa
import pytest

from crosscontract.contracts.schema import DimensionSchema
from crosscontract.contracts.schema.adapters.pandera_adapter import PanderaPandasAdapter


@pytest.fixture
def dimension_schema() -> pa.DataFrameSchema:
    schema = DimensionSchema.model_validate({})
    return PanderaPandasAdapter.convert_schema(schema)


def _make_df(rows: list[dict]) -> pd.DataFrame:
    defaults = {
        "id": "x",
        "level": 0,
        "parent_id": pd.NA,
        "label": pd.NA,
        "description": pd.NA,
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


VALID_TWO_LEVEL = _make_df(
    [
        {"id": "europe", "level": 0},
        {"id": "other", "level": 0},
        {"id": "germany", "level": 1, "parent_id": "europe"},
        {"id": "other_europe", "level": 1, "parent_id": "europe"},
        {"id": "other_other", "level": 1, "parent_id": "other"},
    ]
)


class TestValidDimension:
    def test_valid_two_level_hierarchy_passes(self, dimension_schema):
        result = dimension_schema.validate(VALID_TWO_LEVEL, lazy=True)
        assert len(result) == len(VALID_TWO_LEVEL)

    def test_valid_three_level_hierarchy_passes(self, dimension_schema):
        df = _make_df(
            [
                {"id": "world", "level": 0},
                {"id": "other", "level": 0},
                {"id": "europe", "level": 1, "parent_id": "world"},
                {"id": "other_world", "level": 1, "parent_id": "world"},
                {"id": "other_other", "level": 1, "parent_id": "other"},
                {"id": "germany", "level": 2, "parent_id": "europe"},
                {"id": "other_europe", "level": 2, "parent_id": "europe"},
                {"id": "other_other_world", "level": 2, "parent_id": "other_world"},
                {"id": "other_other_other", "level": 2, "parent_id": "other_other"},
            ]
        )
        result = dimension_schema.validate(df, lazy=True)
        assert len(result) == len(df)


class TestDimensionCheckErrors:
    """Each test triggers exactly one dimension rule through the full adapter
    pipeline."""

    def test_root_with_parent_fails(self, dimension_schema):
        df = VALID_TWO_LEVEL.copy()
        df.loc[df["id"] == "europe", "parent_id"] = "someone"
        with pytest.raises(pa.errors.SchemaErrors, match="Root level"):
            dimension_schema.validate(df, lazy=True)

    def test_child_without_parent_fails(self, dimension_schema):
        df = VALID_TWO_LEVEL.copy()
        df.loc[df["id"] == "germany", "parent_id"] = pd.NA
        with pytest.raises(pa.errors.SchemaErrors, match="sub-level needs a parent"):
            dimension_schema.validate(df, lazy=True)

    def test_child_pointing_to_wrong_level_fails(self, dimension_schema):
        df = _make_df(
            [
                {"id": "world", "level": 0},
                {"id": "other", "level": 0},
                {"id": "europe", "level": 1, "parent_id": "world"},
                {"id": "other_world", "level": 1, "parent_id": "world"},
                {"id": "other_other", "level": 1, "parent_id": "other"},
                # level 2 pointing at level 0 instead of level 1
                {"id": "germany", "level": 2, "parent_id": "world"},
                {"id": "other_europe", "level": 2, "parent_id": "europe"},
                {"id": "other_other_world", "level": 2, "parent_id": "other_world"},
                {"id": "other_other_other", "level": 2, "parent_id": "other_other"},
            ]
        )
        with pytest.raises(pa.errors.SchemaErrors, match="level above"):
            dimension_schema.validate(df, lazy=True)

    def test_missing_root_other_fails(self, dimension_schema):
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "asia", "level": 0},
                {"id": "child", "level": 1, "parent_id": "europe"},
                {"id": "other_europe", "level": 1, "parent_id": "europe"},
                {"id": "other_asia", "level": 1, "parent_id": "asia"},
            ]
        )
        with pytest.raises(pa.errors.SchemaErrors, match="Other entry"):
            dimension_schema.validate(df, lazy=True)

    def test_missing_child_other_fails(self, dimension_schema):
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "other", "level": 0},
                # europe has children but no other_europe
                {"id": "germany", "level": 1, "parent_id": "europe"},
                {"id": "france", "level": 1, "parent_id": "europe"},
                {"id": "other_other", "level": 1, "parent_id": "other"},
            ]
        )
        with pytest.raises(pa.errors.SchemaErrors, match="Other entry"):
            dimension_schema.validate(df, lazy=True)

    def test_wrong_other_naming_fails(self, dimension_schema):
        df = _make_df(
            [
                {"id": "europe", "level": 0},
                {"id": "other", "level": 0},
                {"id": "germany", "level": 1, "parent_id": "europe"},
                # other_asia instead of other_europe
                {"id": "other_asia", "level": 1, "parent_id": "europe"},
                {"id": "other_other", "level": 1, "parent_id": "other"},
            ]
        )
        with pytest.raises(pa.errors.SchemaErrors, match="Other entry"):
            dimension_schema.validate(df, lazy=True)


class TestLazyCollectsMultipleErrors:
    def test_multiple_dimension_errors_collected(self, dimension_schema):
        """Lazy validation should surface all dimension errors, not just the first."""
        df = _make_df(
            [
                # root with parent (violates root_no_parent)
                {"id": "europe", "level": 0, "parent_id": "ghost"},
                # no root "other" (violates other_entries)
                # child without parent (violates parent_id_required)
                {"id": "germany", "level": 1},
            ]
        )
        with pytest.raises(pa.errors.SchemaErrors) as exc_info:
            dimension_schema.validate(df, lazy=True)
        # At minimum we expect more than one DimensionError
        dimension_errors = [
            err
            for err in exc_info.value.schema_errors
            if hasattr(err, "check") and "DimensionError" in str(err.check)
        ]
        assert len(dimension_errors) >= 2
