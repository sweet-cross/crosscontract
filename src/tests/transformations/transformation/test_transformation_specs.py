from typing import Annotated, Union

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
from pydantic import Field, TypeAdapter, ValidationError

from crosscontract.transformations.transformation import (
    DropColumns,
    MapColumnValues,
    RenameColumns,
    drop_columns,
    map_column_values,
    rename_columns,
)

# An ad-hoc union, as a consumer would build it — the leaf ships no union itself.
TransformationUnion = Annotated[
    MapColumnValues | RenameColumns | DropColumns,
    Field(discriminator="type"),
]
_adapter: TypeAdapter = TypeAdapter(TransformationUnion)


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Fixture for a sample DataFrame."""
    return pd.DataFrame(
        {
            "A": [1, 2, 3, 4, 5],
            "B": ["foo", "bar", "baz", "foo", "qux"],
            "C": [10.0, 20.0, 30.0, 40.0, 50.0],
        }
    )


def test_map_column_values_apply_matches_function(sample_df: pd.DataFrame):
    """`MapColumnValues.apply` matches the pure function."""
    spec = MapColumnValues(
        type="map_column_values",
        column_name="A",
        mapping={1: 100, 3: 300},
        default_value=-1,
    )
    expected = map_column_values(sample_df, "A", {1: 100, 3: 300}, -1)
    assert_frame_equal(spec.apply(sample_df), expected)


def test_map_column_values_keep_original_default(sample_df: pd.DataFrame):
    """Omitting `default_value` keeps unmapped values unchanged."""
    spec = MapColumnValues(column_name="B", mapping={"foo": "FOO"})
    result = spec.apply(sample_df)
    assert list(result["B"]) == ["FOO", "bar", "baz", "FOO", "qux"]


def test_rename_columns_apply_matches_function(sample_df: pd.DataFrame):
    """`RenameColumns.apply` matches the pure function."""
    spec = RenameColumns(mapping={"A": "col_A"})
    expected = rename_columns(sample_df, {"A": "col_A"})
    assert_frame_equal(spec.apply(sample_df), expected)


def test_drop_columns_apply_matches_function(sample_df: pd.DataFrame):
    """`DropColumns.apply` matches the pure function."""
    spec = DropColumns(columns=["B"])
    expected = drop_columns(sample_df, ["B"])
    assert_frame_equal(spec.apply(sample_df), expected)


def test_discriminator_resolves_correct_model():
    """The `type` discriminator selects the right model in a union."""
    resolved = _adapter.validate_python(
        {"type": "rename_columns", "mapping": {"A": "col_A"}}
    )
    assert isinstance(resolved, RenameColumns)


def test_extra_keys_forbidden():
    """Unknown keys raise a ValidationError (extra='forbid')."""
    with pytest.raises(ValidationError):
        MapColumnValues(column_name="A", mapping={1: 2}, bogus="x")


def test_unknown_type_rejected():
    """An unknown discriminator value is rejected by the union."""
    with pytest.raises(ValidationError):
        _adapter.validate_python({"type": "does_not_exist", "columns": ["A"]})


def test_ordered_application(sample_df: pd.DataFrame):
    """Chained specs apply in order: map -> rename -> drop."""
    steps = [
        MapColumnValues(column_name="A", mapping={1: 100}),
        RenameColumns(mapping={"A": "col_A"}),
        DropColumns(columns=["B"]),
    ]
    df = sample_df
    for step in steps:
        df = step.apply(df)

    assert "col_A" in df.columns
    assert "A" not in df.columns
    assert "B" not in df.columns
    assert df["col_A"].iloc[0] == 100


def test_rename_after_drop_is_noop_on_missing_column(sample_df: pd.DataFrame):
    """Renaming a dropped column is a silent no-op (order matters)."""
    df = DropColumns(columns=["B"]).apply(sample_df)
    df = RenameColumns(mapping={"B": "col_B"}).apply(df)
    assert "col_B" not in df.columns
