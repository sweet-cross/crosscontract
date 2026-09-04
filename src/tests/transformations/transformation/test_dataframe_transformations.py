from unittest.mock import patch

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from crosscontract.transformations.transformation.dataframe_transformations import (
    DropColumns,
    DropRowsByValue,
    RenameColumns,
    drop_columns,
    drop_rows_by_value,
    rename_columns,
)


class TestRenameColumns:
    @pytest.mark.parametrize(
        "input_df, mapping, expected_df",
        [
            # Basic renaming
            (
                pd.DataFrame({"A": [1], "B": [2], "C": [3]}),
                {"A": "col_A", "C": "col_C"},
                pd.DataFrame({"col_A": [1], "B": [2], "col_C": [3]}),
            ),
            # Empty mapping results in no changes
            (
                pd.DataFrame({"A": [1], "B": [2], "C": [3]}),
                {},
                pd.DataFrame({"A": [1], "B": [2], "C": [3]}),
            ),
            # Renaming columns on an empty DataFrame
            (
                pd.DataFrame(columns=["A", "B"]),
                {"A": "alpha"},
                pd.DataFrame(columns=["alpha", "B"]),
            ),
        ],
        ids=["basic_renaming", "empty_mapping", "empty_dataframe"],
    )
    def test_rename_columns_success(self, input_df, mapping, expected_df):
        """Test successful column renaming scenarios."""
        df_org = input_df.copy()
        result_df = rename_columns(input_df, mapping)

        assert_frame_equal(result_df, expected_df)
        assert_frame_equal(input_df, df_org)  # Ensure original DataFrame is unchanged

    @pytest.mark.parametrize(
        "mapping, expected_error, match_msg",
        [
            # Nonexistent column
            ({"D": "col_D"}, KeyError, None),
            # Mix of existing and nonexistent columns
            ({"A": "col_A", "D": "col_D"}, KeyError, None),
            # Collision: renaming onto an existing column name
            ({"A": "B"}, ValueError, "duplicate column"),
            # Collision: renaming two columns to the same name
            ({"A": "X", "B": "X"}, ValueError, "duplicate column"),
        ],
        ids=[
            "nonexistent_col",
            "mixed_existence",
            "collision_existing",
            "collision_two_sources",
        ],
    )
    def test_rename_columns_raises(self, mapping, expected_error, match_msg):
        """Test that invalid renaming operations raise the correct exceptions."""
        # Define a standard input DataFrame for failure cases
        input_df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})

        with pytest.raises(expected_error, match=match_msg):
            rename_columns(input_df, mapping)

    def test_spec_pass_through(self):
        """Test that the `RenameColumns` spec correctly applies the function."""
        mapping = {"A": "col_A", "B": "col_B"}
        spec = RenameColumns(mapping=mapping)
        with patch(
            "crosscontract.transformations.transformation.dataframe_transformations.rename_columns"
        ) as mock_function:
            spec.apply("a")
            mock_function.assert_called_once_with("a", mapping)


class TestDropColumns:
    @pytest.mark.parametrize(
        "input_df, columns_to_drop, expected_df",
        [
            # Single column
            (
                pd.DataFrame({"A": [1], "B": [2], "C": [3]}),
                ["B"],
                pd.DataFrame({"A": [1], "C": [3]}),
            ),
            # Multiple columns
            (
                pd.DataFrame({"A": [1], "B": [2], "C": [3]}),
                ["A", "C"],
                pd.DataFrame({"B": [2]}),
            ),
            # Empty list results in no changes
            (
                pd.DataFrame({"A": [1], "B": [2], "C": [3]}),
                [],
                pd.DataFrame({"A": [1], "B": [2], "C": [3]}),
            ),
            # Dropping from an empty DataFrame
            (
                pd.DataFrame(columns=["A", "B"]),
                ["A"],
                pd.DataFrame(columns=["B"]),
            ),
        ],
        ids=["single_column", "multiple_columns", "empty_list", "empty_dataframe"],
    )
    def test_drop_columns_success(self, input_df, columns_to_drop, expected_df):
        """Test successful column dropping scenarios."""
        df_org = input_df.copy()
        result_df = drop_columns(input_df, columns_to_drop)

        assert_frame_equal(result_df, expected_df)
        assert_frame_equal(input_df, df_org)  # Ensure original DataFrame is unchanged

    @pytest.mark.parametrize(
        "columns_to_drop, expected_error",
        [
            # Nonexistent column
            (["D"], KeyError),
            # Mix of existing and nonexistent columns
            (["A", "D"], KeyError),
        ],
        ids=["nonexistent_col", "mixed_existence"],
    )
    def test_drop_columns_raises(self, columns_to_drop, expected_error):
        """Test that dropping nonexistent columns raises the correct exceptions."""
        # Standard input DataFrame for failure cases
        input_df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})

        with pytest.raises(expected_error):
            drop_columns(input_df, columns_to_drop)

    def test_spec_pass_through(self):
        """Test that the `DropColumns` spec correctly applies the function."""
        columns_to_drop = ["A", "B"]
        spec = DropColumns(columns=columns_to_drop)
        with patch(
            "crosscontract.transformations.transformation.dataframe_transformations.drop_columns"
        ) as mock_function:
            spec.apply("a")
            mock_function.assert_called_once_with("a", columns_to_drop)


class TestDropRowsByValue:
    @pytest.mark.parametrize(
        "column_name, values_to_drop, expected_df",
        [
            # 1. Drop a single value (removes row index 1)
            (
                "A",
                [2],
                pd.DataFrame({"A": [1, 3, 4], "B": ["w", "y", "z"]}, index=[0, 2, 3]),
            ),
            # 2. Drop multiple values (removes row index 0 and 2)
            (
                "A",
                [1, 3],
                pd.DataFrame({"A": [2, 4], "B": ["x", "z"]}, index=[1, 3]),
            ),
            # 3. Value not present in dataframe (returns identical dataframe)
            (
                "A",
                [99],
                pd.DataFrame({"A": [1, 2, 3, 4], "B": ["w", "x", "y", "z"]}),
            ),
            # 4. Empty values list (returns identical dataframe)
            (
                "A",
                [],
                pd.DataFrame({"A": [1, 2, 3, 4], "B": ["w", "x", "y", "z"]}),
            ),
        ],
        ids=["drop_single", "drop_multiple", "no_match", "empty_list"],
    )
    def test_drop_rows_by_value_success(self, column_name, values_to_drop, expected_df):
        """Test successful row dropping scenarios."""
        # Standard input DataFrame
        input_df = pd.DataFrame({"A": [1, 2, 3, 4], "B": ["w", "x", "y", "z"]})
        df_org = input_df.copy()

        result_df = drop_rows_by_value(input_df, column_name, values_to_drop)

        assert_frame_equal(result_df, expected_df)
        assert_frame_equal(input_df, df_org)  # Ensure original DataFrame is unchanged

    def test_drop_rows_by_value_raises_missing_column(self):
        """Test that dropping based on a nonexistent column raises a KeyError."""
        input_df = pd.DataFrame({"A": [1, 2, 3]})

        with pytest.raises(KeyError):
            drop_rows_by_value(input_df, "NonexistentColumn", [1])

    def test_spec_pass_through(self):
        """Test that the `DropRowsByValue` spec correctly applies the function."""
        spec = DropRowsByValue(column_name="A", values=[1, 2])
        with patch(
            "crosscontract.transformations.transformation.dataframe_transformations.drop_rows_by_value"
        ) as mock_function:
            spec.apply("a")
            mock_function.assert_called_once_with("a", "A", [1, 2])
