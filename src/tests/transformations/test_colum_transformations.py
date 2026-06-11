import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from crosscontract.transformations.column_transformations import (
    KEEP_ORIGINAL,
    map_column_values,
)


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


def test_map_column_values_basic(sample_df: pd.DataFrame):
    """Test basic value mapping in a column."""
    mapping = {1: 100, 3: 300}
    result_df = map_column_values(sample_df, "A", mapping)
    expected_df = sample_df.copy()
    expected_df["A"] = [100.0, 2.0, 300.0, 4.0, 5.0]
    assert_frame_equal(result_df, expected_df)


def test_map_column_values_keep_original(sample_df: pd.DataFrame):
    """Test that unmapped values are kept when default is KEEP_ORIGINAL."""
    mapping = {"foo": "FOO", "baz": "BAZ"}
    result_df = map_column_values(sample_df, "B", mapping, default_value=KEEP_ORIGINAL)
    expected_df = sample_df.copy()
    expected_df["B"] = ["FOO", "bar", "BAZ", "FOO", "qux"]
    assert_frame_equal(result_df, expected_df)


def test_map_column_values_default_none(sample_df: pd.DataFrame):
    """Test that unmapped values are set to None when default_value is None."""
    mapping = {"foo": "FOO", "baz": "BAZ"}
    result_df = map_column_values(sample_df, "B", mapping, default_value=None)
    expected_df = sample_df.copy()
    expected_df["B"] = ["FOO", None, "BAZ", "FOO", None]
    assert_frame_equal(result_df, expected_df)


def test_map_column_values_custom_default(sample_df: pd.DataFrame):
    """Test that unmapped values are set to a custom default value."""
    mapping = {1: 10, 5: 50}
    result_df = map_column_values(sample_df, "A", mapping, default_value=-1)
    expected_df = sample_df.copy()
    expected_df["A"] = [10.0, -1.0, -1.0, -1.0, 50.0]
    assert_frame_equal(result_df, expected_df)


def test_map_column_values_empty_mapping(sample_df: pd.DataFrame):
    """Test that an empty mapping results in no changes."""
    mapping = {}
    result_df = map_column_values(sample_df, "A", mapping)
    assert_frame_equal(result_df, sample_df, check_dtype=False)


def test_map_column_values_with_nan(sample_df: pd.DataFrame):
    """Test mapping with NaN values in the column."""
    df = sample_df.copy()
    df.loc[1, "C"] = pd.NA
    mapping = {10.0: 1.0, 50.0: 5.0}
    result_df = map_column_values(df, "C", mapping, default_value=None)
    expected_df = df.copy()
    expected_df["C"] = [1.0, None, None, None, 5.0]
    assert_frame_equal(result_df, expected_df)


def test_map_column_values_nonexistent_column(sample_df: pd.DataFrame):
    """Test that a KeyError is raised for a nonexistent column."""
    with pytest.raises(KeyError):
        map_column_values(sample_df, "D", {1: 2})


def test_map_column_values_empty_dataframe():
    """Test mapping on an empty DataFrame."""
    df = pd.DataFrame({"A": [], "B": []}, dtype=int)
    mapping = {1: 10}
    result_df = map_column_values(df, "A", mapping)
    assert_frame_equal(result_df, df, check_dtype=False)
