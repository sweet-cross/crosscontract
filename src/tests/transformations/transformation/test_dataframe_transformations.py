import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from crosscontract.transformations.transformation.dataframe_transformations import (
    drop_columns,
    rename_columns,
)


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Fixture for a sample DataFrame."""
    return pd.DataFrame(
        {
            "A": [1, 2, 3],
            "B": ["foo", "bar", "baz"],
            "C": [10.0, 20.0, 30.0],
        }
    )


# Tests for rename_columns
def test_rename_columns_basic(sample_df: pd.DataFrame):
    """Test basic column renaming."""
    mapping = {"A": "col_A", "C": "col_C"}
    result_df = rename_columns(sample_df, mapping)
    expected_df = sample_df.copy()
    expected_df.columns = ["col_A", "B", "col_C"]
    assert_frame_equal(result_df, expected_df)


def test_rename_columns_empty_mapping(sample_df: pd.DataFrame):
    """Test that an empty mapping results in no changes."""
    result_df = rename_columns(sample_df, {})
    assert_frame_equal(result_df, sample_df)


def test_rename_columns_nonexistent_column(sample_df: pd.DataFrame):
    """Test that renaming a nonexistent column does not raise an error and has
    no effect."""
    mapping = {"D": "col_D"}
    result_df = rename_columns(sample_df, mapping)
    assert_frame_equal(result_df, sample_df)


def test_rename_columns_on_empty_dataframe():
    """Test renaming columns on an empty DataFrame."""
    df = pd.DataFrame(columns=["A", "B"])
    mapping = {"A": "alpha"}
    result_df = rename_columns(df, mapping)
    expected_df = pd.DataFrame(columns=["alpha", "B"])
    assert_frame_equal(result_df, expected_df)


# Tests for drop_columns
def test_drop_columns_single(sample_df: pd.DataFrame):
    """Test dropping a single column."""
    result_df = drop_columns(sample_df, ["B"])
    expected_df = sample_df.drop(columns=["B"])
    assert_frame_equal(result_df, expected_df)


def test_drop_columns_multiple(sample_df: pd.DataFrame):
    """Test dropping multiple columns."""
    result_df = drop_columns(sample_df, ["A", "C"])
    expected_df = sample_df.drop(columns=["A", "C"])
    assert_frame_equal(result_df, expected_df)


def test_drop_columns_empty_list(sample_df: pd.DataFrame):
    """Test that dropping an empty list of columns results in no changes."""
    result_df = drop_columns(sample_df, [])
    assert_frame_equal(result_df, sample_df)


def test_drop_columns_nonexistent_column(sample_df: pd.DataFrame):
    """Test that dropping a nonexistent column raises a KeyError."""
    with pytest.raises(KeyError):
        drop_columns(sample_df, ["D"])


def test_drop_columns_mixed_existence(sample_df: pd.DataFrame):
    """Test dropping a mix of existing and nonexistent columns raises a KeyError."""
    with pytest.raises(KeyError):
        drop_columns(sample_df, ["A", "D"])


def test_drop_columns_from_empty_dataframe():
    """Test dropping columns from an empty DataFrame."""
    df = pd.DataFrame(columns=["A", "B"])
    result_df = drop_columns(df, ["A"])
    expected_df = pd.DataFrame(columns=["B"])
    assert_frame_equal(result_df, expected_df)
