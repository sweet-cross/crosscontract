from unittest.mock import patch

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
from pydantic import ValidationError

from crosscontract.transformations.transformation.column_transformations import (
    KEEP_ORIGINAL,
    CastColumn,
    MapColumnValues,
    ParseDatetimeColumn,
    cast_column,
    map_column_values,
    parse_datetime_column,
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


class TestMapColumnValues:
    def test_map_column_values_basic(self, sample_df: pd.DataFrame):
        """Test basic value mapping in a column."""
        mapping = {1: 100, 3: 300}
        result_df = map_column_values(sample_df, "A", mapping)
        expected_df = sample_df.copy()
        expected_df["A"] = [100.0, 2.0, 300.0, 4.0, 5.0]
        assert_frame_equal(result_df, expected_df)

    def test_map_column_values_keep_original(self, sample_df: pd.DataFrame):
        """Test that unmapped values are kept when default is KEEP_ORIGINAL."""
        mapping = {"foo": "FOO", "baz": "BAZ"}
        result_df = map_column_values(
            sample_df, "B", mapping, default_value=KEEP_ORIGINAL
        )
        expected_df = sample_df.copy()
        expected_df["B"] = ["FOO", "bar", "BAZ", "FOO", "qux"]
        assert_frame_equal(result_df, expected_df)

    def test_map_column_values_default_none(self, sample_df: pd.DataFrame):
        """Test that unmapped values are set to None when default_value is None."""
        mapping = {"foo": "FOO", "baz": "BAZ"}
        result_df = map_column_values(sample_df, "B", mapping, default_value=None)
        expected_df = sample_df.copy()
        expected_df["B"] = ["FOO", None, "BAZ", "FOO", None]
        assert_frame_equal(result_df, expected_df)

    def test_map_column_values_custom_default(self, sample_df: pd.DataFrame):
        """Test that unmapped values are set to a custom default value."""
        mapping = {1: 10, 5: 50}
        result_df = map_column_values(sample_df, "A", mapping, default_value=-1)
        expected_df = sample_df.copy()
        expected_df["A"] = [10.0, -1.0, -1.0, -1.0, 50.0]
        assert_frame_equal(result_df, expected_df)

    def test_map_column_values_empty_mapping(self, sample_df: pd.DataFrame):
        """Test that an empty mapping results in no changes."""
        mapping = {}
        result_df = map_column_values(sample_df, "A", mapping)
        assert_frame_equal(result_df, sample_df, check_dtype=False)

    def test_map_column_values_with_nan(self, sample_df: pd.DataFrame):
        """Test mapping with NaN values in the column."""
        df = sample_df.copy()
        df.loc[1, "C"] = pd.NA
        mapping = {10.0: 1.0, 50.0: 5.0}
        result_df = map_column_values(df, "C", mapping, default_value=None)
        expected_df = df.copy()
        expected_df["C"] = [1.0, None, None, None, 5.0]
        assert_frame_equal(result_df, expected_df)

    def test_map_column_values_maps_to_none_distinct_from_unmapped(
        self,
        sample_df: pd.DataFrame,
    ):
        """A value intentionally mapped to None is kept, not treated as unmapped.

        With KEEP_ORIGINAL, only values absent from the mapping keys fall back to
        the original. A key that maps to None must yield None, while unmapped
        values retain their original value.
        """
        mapping = {"foo": None, "baz": "BAZ"}
        result_df = map_column_values(
            sample_df, "B", mapping, default_value=KEEP_ORIGINAL
        )
        expected_df = sample_df.copy()
        expected_df["B"] = [None, "bar", "BAZ", None, "qux"]
        assert_frame_equal(result_df, expected_df)

    def test_map_column_values_nonexistent_column(self, sample_df: pd.DataFrame):
        """Test that a KeyError is raised for a nonexistent column."""
        with pytest.raises(KeyError):
            map_column_values(sample_df, "D", {1: 2})

    def test_map_column_values_empty_dataframe(self):
        """Test mapping on an empty DataFrame."""
        df = pd.DataFrame({"A": [], "B": []}, dtype=int)
        mapping = {1: 10}
        result_df = map_column_values(df, "A", mapping)
        assert_frame_equal(result_df, df, check_dtype=False)

    def test_map_column_values_non_string_column_label(self):
        """A non-string column label is supported and the input is not mutated."""
        df = pd.DataFrame({1: ["a", "b", "c"], "B": [10, 20, 30]})
        result_df = map_column_values(df, 1, {"a": "A", "c": "C"})
        assert list(result_df[1]) == ["A", "b", "C"]
        # input left unmutated
        assert list(df[1]) == ["a", "b", "c"]

    def test_spec_default_value_is_keep_original(self, sample_df: pd.DataFrame):
        """The default value for `MapColumnValues` is KEEP_ORIGINAL."""
        mapping = {"foo": "FOO", "baz": "BAZ"}
        spec = MapColumnValues(column_name="B", mapping=mapping)
        result_df = spec.apply(sample_df)
        expected_df = sample_df.copy()
        expected_df["B"] = expected_df["B"].map(lambda x: mapping.get(x, x))
        assert_frame_equal(result_df, expected_df)

    def test_spec_default_value_is_custom(self, sample_df: pd.DataFrame):
        """The default value for `MapColumnValues` is custom value."""
        mapping = {"foo": "FOO", "baz": "BAZ"}
        spec = MapColumnValues(
            column_name="B", mapping=mapping, default_value="DEFAULT"
        )
        result_df = spec.apply(sample_df)
        expected_df = sample_df.copy()
        expected_df["B"] = expected_df["B"].map(lambda x: mapping.get(x, "DEFAULT"))
        assert_frame_equal(result_df, expected_df)

    def test_spec_accepts_custom_default_value_none(self, sample_df: pd.DataFrame):
        """`MapColumnValues` accepts a custom default value."""
        mapping = {"foo": "FOO", "baz": "BAZ", "bar": "BAR"}
        spec = MapColumnValues(column_name="B", mapping=mapping, default_value=None)
        result_df = spec.apply(sample_df)
        expected_df = sample_df.copy()
        expected_df["B"] = expected_df["B"].map(lambda x: mapping.get(x, None))
        assert_frame_equal(result_df, expected_df)

    @pytest.mark.parametrize(
        "default",
        [KEEP_ORIGINAL, None, "DEFAULT"],
        ids=["keep_original", "none", "default"],
    )
    def test_spec_round_trip(self, default):
        """Dumping and reloading a `MapColumnValues` spec retains the same
        attributes."""
        mapping = {"foo": "FOO", "baz": "BAZ"}
        spec = MapColumnValues(column_name="B", mapping=mapping, default_value=default)
        dumped = spec.model_dump()
        reloaded_spec = MapColumnValues.model_validate(dumped)
        assert spec == reloaded_spec
        dumped_json = spec.model_dump_json()
        reloaded_spec_from_json = MapColumnValues.model_validate_json(dumped_json)
        assert spec == reloaded_spec_from_json


class TestCastColumn:
    @pytest.mark.parametrize(
        "to_type, input, expected, dtype",
        [
            ("integer", ["1", "2"], [1, 2], "Int64"),
            ("integer", ["1.0", "2.0"], [1, 2], "Int64"),
            ("integer", [1, 2], [1, 2], "Int64"),
            ("integer", [1.0, 2.0], [1, 2], "Int64"),
            ("integer", ["1.0", 2.0], [1, 2], "Int64"),
            ("number", ["1", "2"], [1.0, 2.0], "Float64"),
            ("number", ["1.0", "2.0"], [1.0, 2.0], "Float64"),
            ("number", [1, 2], [1.0, 2.0], "Float64"),
            ("number", ["1", 2], [1.0, 2.0], "Float64"),
            ("number", [1.0, 2.0], [1.0, 2.0], "Float64"),
            ("string", [1, 2], ["1", "2"], "string"),
            ("string", [1.0, 2.0], ["1.0", "2.0"], "string"),
            ("string", ["a", "b"], ["a", "b"], "string"),
            ("boolean", [1, 0], [True, False], "boolean"),
            ("boolean", [True, False], [True, False], "boolean"),
        ],
    )
    def test_cast_success(self, to_type, input, expected, dtype):
        """Test casting a column to numeric type."""
        df = pd.DataFrame({"A": input, "B": ["x"] * len(input)})
        df_org = pd.DataFrame({"A": input, "B": ["x"] * len(input)})
        df_result = cast_column(df, "A", to_type)
        df_expected = pd.DataFrame({"A": expected, "B": ["x"] * len(expected)})
        df_expected = df_expected.astype({"A": dtype})
        assert_frame_equal(df_result, df_expected)
        assert_frame_equal(df, df_org)  # Ensure original DataFrame is unchanged

    @pytest.mark.parametrize(
        "to_type, input, expected_error",
        [
            ("integer", [1.1, 2.0], TypeError),
            ("integer", ["1.1", 2], TypeError),
            ("integer", ["a", 2], ValueError),
            ("number", ["a", 2], ValueError),
            ("boolean", ["a", 2], TypeError),
            ("unsupported", ["a", 2], ValueError),
        ],
    )
    def test_raises_conversion_not_possible(self, to_type, input, expected_error):
        """Test that casting raises ValueError if not convertible."""
        df = pd.DataFrame({"A": input, "B": ["x"] * len(input)})
        with pytest.raises(expected_error):
            cast_column(df, "A", to_type)

    def test_raises_datetime(self):
        """Test that casting to datetime raises ValueError."""
        df = pd.DataFrame({"A": ["2023-01-01"], "B": ["x"]})
        with pytest.raises(ValueError, match="`parse_datetime_column`"):
            cast_column(df, "A", "datetime")

    def test_spec_rejects_datetime_at_load(self):
        """`datetime` is outside `CastableType`, so the spec fails at load.

        The function keeps a pointed error for direct callers, but a spec must
        never validate and then fail at `apply()` time.
        """
        with pytest.raises(ValidationError):
            CastColumn(column_name="A", to_type="datetime")

    def test_spec_cast_column(self, sample_df: pd.DataFrame):
        """Test that the `CastColumn` spec correctly casts a column."""
        spec = CastColumn(column_name="A", to_type="string")
        result_df = spec.apply(sample_df)
        expected_df = sample_df.copy()
        expected_df["A"] = expected_df["A"].astype("string")
        assert_frame_equal(result_df, expected_df)


class TestParseDatetimeColumn:
    @pytest.mark.parametrize(
        "input, kwargs, expected",
        [
            # 1. Proves basic wiring works on the target column
            (
                ["2023-01-01", "2023-01-02"],
                {},
                [pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-02")],
            ),
            # 2. Proves the `dayfirst` argument is actually passed down to pandas
            (
                ["01/02/2023", "02/02/2023"],
                {"dayfirst": True},
                [pd.Timestamp("2023-02-01"), pd.Timestamp("2023-02-02")],
            ),
            # 3. Proves the `format` argument is actually passed down to pandas
            (
                ["20231231", "20240101"],
                {"format": "%Y%m%d"},
                [pd.Timestamp("2023-12-31"), pd.Timestamp("2024-01-01")],
            ),
        ],
    )
    def test_parse_datetime_contract(self, input, kwargs, expected):
        """Test that the function applies pandas conversion, respects kwargs, and
        doesn't mutate."""
        # Setup: Dataframe with target column "A" and an untouched column "B"
        df = pd.DataFrame({"A": input, "B": ["untouched", "untouched"]})
        df_org = df.copy(deep=True)

        # Execute
        df_result = parse_datetime_column(df, "A", **kwargs)

        # Assert expected conversion on column "A"
        expected_series = pd.Series(expected, name="A")
        pd.testing.assert_series_equal(df_result["A"], expected_series)

        # Assert column "B" was untouched
        pd.testing.assert_series_equal(df_result["B"], df_org["B"])

        # Assert original DataFrame was strictly not mutated
        assert_frame_equal(df, df_org)

    def test_raises_parse_error_on_invalid_data(self):
        """Proves that exceptions from pandas bubble up correctly."""
        df = pd.DataFrame({"A": ["not_a_date"]})
        with pytest.raises(ValueError):
            parse_datetime_column(df, "A")

    def test_spec_pass_through(self):
        """Test that the `ParseDatetimeColumn` spec correctly applies the function."""
        spec = ParseDatetimeColumn(column_name="A", dayfirst=True, format="%Y-%m-%d")
        with patch(
            "crosscontract.transformations.transformation.column_transformations.parse_datetime_column"
        ) as mock_function:
            spec.apply("df")
            mock_function.assert_called_once_with(
                "df",
                "A",
                dayfirst=True,
                format="%Y-%m-%d",
            )
