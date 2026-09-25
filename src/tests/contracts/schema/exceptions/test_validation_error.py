import json
from unittest.mock import patch

import pandas as pd
import pandera.pandas as pa
import pytest

from crosscontract.contracts.schema import TableSchema
from crosscontract.contracts.schema.exceptions.validation_error import (
    SchemaValidationError,
)


class MockSchemaErrors(pa.errors.SchemaErrors):
    """Mock object mimicking pandera.errors.SchemaErrors structure."""

    def __init__(self, failure_cases: pd.DataFrame, data: pd.DataFrame):
        # Bypass the real __init__ entirely
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

    def test_no_schema_errors(self):
        """Test behavior when no schema_errors are provided."""
        error = SchemaValidationError("No Schema Errors")
        parsed = error.errors
        assert parsed == []

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


def _error_from_rows(
    rows: list[tuple[str, str, int, object]],
) -> SchemaValidationError:
    """Build an error from `(schema_context, check, index, failure_case)` rows,
    all on column `c`."""
    failure_cases = pd.DataFrame(
        rows, columns=["schema_context", "check", "index", "failure_case"]
    ).assign(column="c")
    mock_errors = MockSchemaErrors(failure_cases, pd.DataFrame())
    return SchemaValidationError("Test", mock_errors)


def _validation_error(
    schema: dict, df: pd.DataFrame, **kwargs
) -> SchemaValidationError:
    """Validate `df` against `schema` and return the raised error."""
    with pytest.raises(SchemaValidationError) as exc_info:
        TableSchema.model_validate(schema).validate_dataframe(df, **kwargs)
    return exc_info.value


class TestMaxErrors:
    """Tests for condensing the report with `max_errors`."""

    def test_default_is_unchanged(self):
        """Without `max_errors`, the full report comes back without a `count`."""
        error = _error_from_rows(
            [("Column", "isin", 0, "x"), ("Column", "isin", 1, "x")]
        )

        assert error.to_list() == error.errors
        assert error.to_list(max_errors=None) == error.errors
        assert len(error.to_list()) == 2
        assert all("count" not in row for row in error.to_list())

    def test_repeated_values_are_merged(self):
        """Repeats of a value merge into its first row, which counts them."""
        error = _error_from_rows(
            [
                ("Column", "isin", 0, "x"),
                ("Column", "isin", 1, "y"),
                ("Column", "isin", 2, "x"),
                ("Column", "isin", 3, "x"),
                ("Column", "isin", 4, "y"),
            ]
        )

        condensed = error.to_list(max_errors=10)

        assert [(r["failure_case"], r["index"], r["count"]) for r in condensed] == [
            ("x", 0, 3),
            ("y", 1, 2),
        ]

    def test_same_value_in_different_checks_is_not_merged(self):
        """A value is merged only within its own check."""
        error = _error_from_rows(
            [("Column", "check_a", 0, "x"), ("Column", "check_b", 0, "x")]
        )

        condensed = error.to_list(max_errors=10)

        assert [(r["check"], r["count"]) for r in condensed] == [
            ("check_a", 1),
            ("check_b", 1),
        ]

    def test_limit_applies_per_check_and_column(self):
        """Each check and column keeps at most `max_errors` distinct values."""
        error = _error_from_rows(
            [("Column", "check_a", i, f"a{i}") for i in range(4)]
            + [("Column", "check_b", i, f"b{i}") for i in range(4)]
        )

        condensed = error.to_list(max_errors=2)

        assert [r["failure_case"] for r in condensed] == ["a0", "a1", "b0", "b1"]

    def test_repeats_of_a_kept_value_count_beyond_the_limit(self):
        """Once the limit is reached, new values are dropped, while repeats of
        a kept value still add to its count."""
        error = _error_from_rows(
            [
                ("Column", "isin", 0, "a"),
                ("Column", "isin", 1, "b"),
                ("Column", "isin", 2, "c"),
                ("Column", "isin", 3, "a"),
            ]
        )

        condensed = error.to_list(max_errors=2)

        assert [(r["failure_case"], r["count"]) for r in condensed] == [
            ("a", 2),
            ("b", 1),
        ]

    def test_limit_applies_to_table_level_errors(self):
        """Errors reported on the whole table are limited like column errors."""
        error = _error_from_rows(
            [("DataFrameSchema", "unique", i, f"k{i}") for i in range(5)]
        )

        condensed = error.to_list(max_errors=3)

        assert [r["failure_case"] for r in condensed] == ["k0", "k1", "k2"]

    def test_nulls_are_merged(self):
        """`None`, `NaN` and `""` in a required column merge into one row."""
        error = _validation_error(
            {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "x", "type": "number", "constraints": {"required": True}},
                ]
            },
            pd.DataFrame({"id": ["a", "b", "c"], "x": [None, float("nan"), ""]}),
        )

        condensed = error.to_list(max_errors=10)

        assert len(condensed) == 1
        assert condensed[0]["failure_case"] is None
        assert condensed[0]["index"] == 0
        assert condensed[0]["count"] == 3

    def test_list_values_are_merged(self):
        """An unhashable failing value is merged and keeps its original value."""
        error = _validation_error(
            {
                "fields": [
                    {"name": "id", "type": "string"},
                    {
                        "name": "tags",
                        "type": "list",
                        "itemType": "integer",
                        "constraints": {"maxLength": 2},
                    },
                ]
            },
            pd.DataFrame({"id": ["a", "b", "c"], "tags": [[1, 2, 3], [1, 2, 3], [1]]}),
        )

        condensed = error.to_list(max_errors=10)

        assert len(condensed) == 1
        assert condensed[0]["failure_case"] == [1, 2, 3]
        assert condensed[0]["index"] == 0
        assert condensed[0]["count"] == 2

    def test_tuple_holding_a_list_is_merged(self):
        """A tuple holding a list, as a key over a list column reports it, is
        merged and keeps its original value."""
        error = _error_from_rows(
            [
                ("DataFrameSchema", "unique", 0, ("a", [1, 2])),
                ("DataFrameSchema", "unique", 1, ("a", [1, 2])),
            ]
        )

        condensed = error.to_list(max_errors=10)

        assert len(condensed) == 1
        assert condensed[0]["failure_case"] == ("a", [1, 2])
        assert condensed[0]["index"] == 0
        assert condensed[0]["count"] == 2

    def test_duplicated_primary_key_is_merged(self):
        """A primary key occurring three times becomes one row counting three."""
        error = _validation_error(
            {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "y", "type": "integer"},
                ],
                "primaryKey": ["id"],
            },
            pd.DataFrame({"id": ["a", "a", "a", "b"], "y": [1, 2, 3, 4]}),
            primary_key_values=[],
        )

        condensed = error.to_list(max_errors=10)

        assert len(condensed) == 1
        assert condensed[0]["schema_context"] == "DataFrameSchema"
        assert condensed[0]["failure_case"] == ("a",)
        assert condensed[0]["count"] == 3

    def test_duplicated_primary_keys_are_limited(self):
        """More distinct duplicated keys than `max_errors` are cut to the limit."""
        error = _validation_error(
            {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "y", "type": "integer"},
                ],
                "primaryKey": ["id"],
            },
            pd.DataFrame({"id": ["a", "a", "b", "b", "c", "c"], "y": range(6)}),
            primary_key_values=[],
        )

        condensed = error.to_list(max_errors=2)

        assert [(r["failure_case"], r["count"]) for r in condensed] == [
            (("a",), 2),
            (("b",), 2),
        ]

    def test_cached_errors_are_not_mutated(self):
        """A condensed report leaves the full report untouched."""
        error = _error_from_rows(
            [
                ("Column", "isin", 0, "x"),
                ("Column", "isin", 1, "x"),
                ("Column", "isin", 2, "y"),
            ]
        )
        full = [dict(row) for row in error.to_list()]

        error.to_list(max_errors=1)

        assert error.to_list() == full
        assert all("count" not in row for row in error.errors)

    @pytest.mark.parametrize("max_errors", [0, -1])
    def test_max_errors_below_one_raises(self, max_errors):
        """A limit below 1 is rejected."""
        error = _error_from_rows([("Column", "isin", 0, "x")])

        with pytest.raises(ValueError, match="`max_errors` must be at least 1"):
            error.to_list(max_errors=max_errors)

    def test_to_pandas_matches_to_list(self):
        """`to_pandas(max_errors)` holds the rows of `to_list(max_errors)`."""
        error = _error_from_rows(
            [
                ("Column", "isin", 0, "x"),
                ("Column", "isin", 1, "x"),
                ("Column", "isin", 2, "y"),
            ]
        )

        pd.testing.assert_frame_equal(
            error.to_pandas(max_errors=1),
            pd.DataFrame(error.to_list(max_errors=1)),
        )
        assert error.to_pandas(max_errors=1)["count"].tolist() == [2]


class TestMissingKeyValues:
    """Tests for reporting missing values in a key's failing values."""

    @pytest.mark.parametrize(
        ("field_type", "values"),
        [
            ("string", ["a", None]),
            ("integer", [1, None]),
            ("datetime", ["2024-01-01 00:00", None]),
        ],
    )
    def test_missing_key_value_is_reported_as_none(self, field_type, values):
        """A missing key value appears as `None` in the tuple, so the report is
        JSON-safe."""
        error = _validation_error(
            {"fields": [{"name": "id", "type": field_type}], "primaryKey": ["id"]},
            pd.DataFrame({"id": values}),
            primary_key_values=[],
        )

        assert [row["failure_case"] for row in error.to_list()] == [(None,)]
        json.dumps(error.to_list(), allow_nan=False)

    @pytest.mark.parametrize(
        ("codes", "ids", "expected"),
        [(["a", "b"], [1, None], ("b", None)), (["a", None], [1, 2], (None, 2))],
    )
    def test_only_missing_value_in_composite_key_is_none(self, codes, ids, expected):
        """In a composite key, only the missing value becomes `None`; the other
        values of the row are reported as they are."""
        error = _validation_error(
            {
                "fields": [
                    {"name": "code", "type": "string"},
                    {"name": "id", "type": "integer"},
                ],
                "primaryKey": ["code", "id"],
            },
            pd.DataFrame({"code": codes, "id": ids}),
            primary_key_values=[],
        )

        assert [row["failure_case"] for row in error.to_list()] == [expected]

    def test_list_key_value_is_kept(self):
        """A list in a key over a list column is reported as it is."""
        error = _validation_error(
            {
                "fields": [{"name": "id", "type": "list", "itemType": "integer"}],
                "primaryKey": ["id"],
            },
            pd.DataFrame({"id": [[1], [1]]}),
            primary_key_values=[],
        )

        assert [row["failure_case"] for row in error.to_list()] == [([1],), ([1],)]


class TestSchemaErrorConversion:
    """Tests for converting SchemaError (singular) to SchemaErrors (plural)."""

    def test_convert_schema_errors_passthrough(self):
        """SchemaErrors (plural) is returned as-is."""
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

        result = SchemaValidationError._convert_schema_error(mock_errors)
        assert result is mock_errors

    def test_convert_invalid_type_raises(self):
        """Passing an unsupported type raises TypeError."""
        with pytest.raises(TypeError, match="Expected SchemaError or SchemaErrors"):
            SchemaValidationError._convert_schema_error("not_an_error")

    def test_singular_schema_error_is_converted(self):
        """A real SchemaError (singular) is converted to SchemaErrors with
        the full failure_cases structure."""
        import pandera.pandas as pa

        schema = pa.DataFrameSchema({"age": pa.Column(int, pa.Check.in_range(0, 150))})
        df = pd.DataFrame({"age": [200]})

        with pytest.raises(pa.errors.SchemaError) as exc_info:
            schema.validate(df, lazy=False)

        singular = exc_info.value
        converted = SchemaValidationError._convert_schema_error(singular)

        assert isinstance(converted, pa.errors.SchemaErrors)
        assert "check" in converted.failure_cases.columns
        assert "column" in converted.failure_cases.columns
        assert "schema_context" in converted.failure_cases.columns
        assert len(converted.failure_cases) == 1

    def test_parsing_works_with_singular_error(self):
        """SchemaValidationError parsing pipeline works end-to-end when
        initialized with a singular SchemaError."""
        import pandera.pandas as pa

        schema = pa.DataFrameSchema({"age": pa.Column(int, pa.Check.in_range(0, 150))})
        df = pd.DataFrame({"age": [200]})

        with pytest.raises(pa.errors.SchemaError) as exc_info:
            schema.validate(df, lazy=False)

        error = SchemaValidationError("Validation failed", exc_info.value)
        parsed = error.errors

        assert len(parsed) == 1
        assert parsed[0]["check"] == "in_range(0, 150)"
        assert parsed[0]["column"] == "age"
        assert parsed[0]["failure_case"] == 200

    def test_parsing_equivalent_for_singular_and_plural(self):
        """Parsing produces the same result regardless of whether the input
        was a SchemaError or SchemaErrors."""
        import pandera.pandas as pa

        schema = pa.DataFrameSchema({"age": pa.Column(int, pa.Check.in_range(0, 150))})
        df = pd.DataFrame({"age": [200]})

        # Singular
        with pytest.raises(pa.errors.SchemaError) as exc_singular:
            schema.validate(df, lazy=False)

        # Plural
        with pytest.raises(pa.errors.SchemaErrors) as exc_plural:
            schema.validate(df, lazy=True)

        error_from_singular = SchemaValidationError("fail", exc_singular.value)
        error_from_plural = SchemaValidationError("fail", exc_plural.value)

        assert error_from_singular.errors == error_from_plural.errors

    def test_reference_error_with_no_extractable_cols(self):
        """Test reference error where check name has no bracketed columns."""
        check_name = "ForeignKeyError: malformed"  # no brackets

        failure_cases = pd.DataFrame(
            {
                "check": [check_name],
                "column": ["col_a"],
                "index": [0],
                "failure_case": ["val_a"],
            }
        )
        data = pd.DataFrame({"col_a": ["val_a"]})
        mock_errors = MockSchemaErrors(failure_cases, data)

        error = SchemaValidationError("Ref Error", mock_errors)
        parsed = error.errors

        assert len(parsed) == 1
        assert parsed[0]["failure_case"] == "val_a"

    def test_reference_error_with_empty_data(self):
        """Test reference error parsing when the attached data is empty."""
        check_name = "ForeignKeyError: ['col_a']"
        failure_cases = pd.DataFrame(
            {
                "check": [check_name],
                "column": ["col_a"],
                "index": [0],
                "failure_case": ["val_missing"],
            }
        )
        # Empty dataframe to trigger the `False` branch of the condition
        data = pd.DataFrame()
        mock_errors = MockSchemaErrors(failure_cases, data)

        error = SchemaValidationError("Ref Error", mock_errors)
        parsed = error.errors

        assert len(parsed) == 1
        # Since data was empty, it skips lookup and retains the original values
        assert parsed[0]["column"] == "col_a"
        assert parsed[0]["failure_case"] == "val_missing"


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

    def test_extract_cols_no_match(self):
        """Test _extract_cols when regex finds no brackets."""
        assert SchemaValidationError._extract_cols("no_brackets_here") == []
