from unittest.mock import patch

import pandas as pd

from crosscontract.contracts.schema.exceptions.validation_error import (
    SchemaValidationError,
)


class MockSchemaErrors:
    """Mock object mimicking pandera.errors.SchemaErrors structure."""

    def __init__(self, failure_cases: pd.DataFrame, data: pd.DataFrame):
        self.failure_cases = failure_cases
        self.data = data


class TestSchemaValidationError:
    """Group tests for SchemaValidationError."""

    def test_initialization(self):
        """Test basic initialization of SchemaValidationError."""
        error = SchemaValidationError("Test Error")
        assert error.message == "Test Error"
        assert error._schema_errors is None
        assert error._parsed_errors is None

    def test_lazy_loading(self):
        """Test that errors are parsed only when accessed."""
        failure_cases = pd.DataFrame(
            {
                "check": ["check1"],
                "column": ["col1"],
                "index": [0],
                "failure_case": ["fail"],
            }
        )
        data = pd.DataFrame({"col1": ["val"]})
        mock_errors = MockSchemaErrors(failure_cases, data)

        error = SchemaValidationError("Test Error", mock_errors)
        assert error._parsed_errors is None

        # Access errors to trigger parsing
        parsed = error.errors
        assert parsed is not None
        assert len(parsed) == 1
        assert error._parsed_errors is parsed

    def test_caching(self):
        """Test that parsed errors are cached."""
        failure_cases = pd.DataFrame(
            {
                "check": ["check1"],
                "column": ["col1"],
                "index": [0],
                "failure_case": ["fail"],
            }
        )
        data = pd.DataFrame({"col1": ["val"]})
        mock_errors = MockSchemaErrors(failure_cases, data)
        error = SchemaValidationError("Test Error", mock_errors)

        first_access = error.errors
        second_access = error.errors
        assert first_access is second_access

    def test_redundant_dtype_filtering(self):
        """Test that redundant dtype errors are removed when coerce_dtype fails."""
        # Scenario: coerce_dtype failure causes a dtype check failure too.
        # We want to keep coerce_dtype and remove dtype for that column.
        failure_cases = pd.DataFrame(
            {
                "check": ["coerce_dtype('int64')", "dtype('int64')", "check_something"],
                "column": ["age", "age", "other_col"],
                "index": [0, 0, 0],
                "failure_case": ["not_int", "not_int", "fail"],
            }
        )
        data = pd.DataFrame({"age": ["not_int"], "other_col": ["val"]})
        mock_errors = MockSchemaErrors(failure_cases, data)

        error = SchemaValidationError("Test Error", mock_errors)
        parsed = error.errors

        # Should have coerce_dtype and check_something, but NOT dtype for age
        checks = [e["check"] for e in parsed]
        assert "coerce_dtype('int64')" in checks
        assert "check_something" in checks
        assert "dtype('int64')" not in checks
        assert len(parsed) == 2

    def test_reference_error_parsing(self):
        """Test parsing of ForeignKeyError and PrimaryKeyError."""
        # Scenario: ForeignKeyError on multiple columns
        check_name = "ForeignKeyError: ['col_a', 'col_b']"

        # failure_cases usually has one row per column involved in the check
        # or duplicates. The code handles duplicates.
        failure_cases = pd.DataFrame(
            {
                "check": [check_name, check_name],
                "column": ["col_a", "col_b"],
                "index": [0, 0],
                "failure_case": ["val_a", "val_b"],
            }
        )

        # Data that failed
        data = pd.DataFrame({"col_a": ["val_a", "ok"], "col_b": ["val_b", "ok"]})

        mock_errors = MockSchemaErrors(failure_cases, data)
        error = SchemaValidationError("Ref Error", mock_errors)
        parsed = error.errors

        assert len(parsed) == 1
        err = parsed[0]
        assert err["check"] == check_name
        # The code joins columns
        assert err["column"] == "col_a, col_b"
        # The code looks up values from data and returns them as a tuple
        assert err["failure_case"] == ("val_a", "val_b")

    def test_lookup_key_error(self):
        """Test handling of KeyError during value lookup."""
        # Scenario: Index in failure_cases does not exist in data
        check_name = "ForeignKeyError: ['col_a']"
        failure_cases = pd.DataFrame(
            {
                "check": [check_name],
                "column": ["col_a"],
                "index": [99],  # Index 99 does not exist in data
                "failure_case": ["val_missing"],
            }
        )
        data = pd.DataFrame({"col_a": ["val"]}, index=[0])
        mock_errors = MockSchemaErrors(failure_cases, data)

        error = SchemaValidationError("Ref Error", mock_errors)
        parsed = error.errors

        assert len(parsed) == 1
        # Should fall back to original values since lookup failed
        assert parsed[0]["column"] == "col_a"
        assert parsed[0]["failure_case"] == "val_missing"

    def test_lookup_duplicated_indices(self):
        """Test handling of duplicated indices in source data."""
        check_name = "ForeignKeyError: ['col_a']"
        failure_cases = pd.DataFrame(
            {
                "check": [check_name],
                "column": ["col_a"],
                "index": [0],
                "failure_case": ["val"],
            }
        )
        # Data has duplicated index 0
        data = pd.DataFrame({"col_a": ["val", "val_dup"]}, index=[0, 0])
        mock_errors = MockSchemaErrors(failure_cases, data)

        error = SchemaValidationError("Ref Error", mock_errors)
        parsed = error.errors

        assert len(parsed) == 1
        # Should handle duplication and return tuple (from lookup)
        assert parsed[0]["failure_case"] == ("val",)

    def test_to_dict_and_pandas(self):
        """Test to_dict and to_pandas methods."""
        failure_cases = pd.DataFrame(
            {
                "check": ["check1"],
                "column": ["col1"],
                "index": [0],
                "failure_case": ["fail"],
            }
        )
        data = pd.DataFrame({"col1": ["val"]})
        mock_errors = MockSchemaErrors(failure_cases, data)
        error = SchemaValidationError("Test", mock_errors)

        # to_dict
        assert error.to_list() == error.errors
        assert isinstance(error.to_list(), list)

        # to_pandas
        df = error.to_pandas()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df.iloc[0]["check"] == "check1"


class TestExtractCols:
    """Group tests for the static method _extract_cols."""

    def test_extract_cols(self):
        """Test the static method _extract_cols."""
        assert SchemaValidationError._extract_cols("ForeignKeyError: ['a', 'b']") == [
            "a",
            "b",
        ]
        assert SchemaValidationError._extract_cols("SomeCheck") == []
        assert SchemaValidationError._extract_cols("Check['a']") == ["a"]

    def test_extract_cols_malformed(self):
        """Test _extract_cols with malformed list string."""
        # Regex matches [...], but content is invalid python literal
        assert SchemaValidationError._extract_cols("Check[1, 2 invalid]") == []

    def test_extract_cols_value_error(self):
        """Test _extract_cols catching ValueError."""
        with patch("ast.literal_eval", side_effect=ValueError):
            assert SchemaValidationError._extract_cols("Check['a']") == []

    def test_extract_cols_syntax_error(self):
        """Test _extract_cols catching SyntaxError."""
        with patch("ast.literal_eval", side_effect=SyntaxError):
            assert SchemaValidationError._extract_cols("Check['a']") == []

    def test_lookup_values_pandas_deduplication(self):
        """Directly test _lookup_values_pandas with duplicated indices."""
        error = SchemaValidationError("msg")
        # Data has duplicated index 0
        data = pd.DataFrame({"col": ["val1", "val2"]}, index=[0, 0])
        indices = pd.Series([0])
        cols = ["col"]

        # This calls the method directly
        result = error._lookup_values_pandas(data, indices, cols)

        # Should return only one value because indices has length 1
        # And it should take the first one because keep="first"
        assert len(result) == 1
        assert result[0] == ("val1",)
