"""Integration tests for PanderaPandasAdapter with DataFrame validation."""

import pandas as pd
import pandera.pandas as pa
import pytest

from crosscontract.contracts.schema import TableSchema
from crosscontract.contracts.schema.adapters.pandera_adapter import PanderaPandasAdapter


@pytest.fixture
def pandera_schema() -> pa.DataFrameSchema:
    """Schema with one field of each type and mixed constraints."""
    fields = [
        {
            "name": "year",
            "type": "integer",
            "constraints": {"required": True, "minimum": 2000, "maximum": 2025},
        },
        {
            "name": "score",
            "type": "number",
            "constraints": {"required": True, "minimum": 0.0, "maximum": 100.0},
        },
        {
            "name": "country",
            "type": "string",
            "constraints": {"required": False, "minLength": 2, "maxLength": 3},
        },
        {
            "name": "created_at",
            "type": "datetime",
            "constraints": {
                "required": True,
                "minimum": "2023-01-01 00:00",
                "maximum": "2025-12-31 23:59",
            },
        },
    ]
    schema = TableSchema.model_validate({"fields": fields})
    return PanderaPandasAdapter.convert_schema(schema)


@pytest.fixture
def valid_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "year": [2020, 2021],
            "score": [55.5, 99.0],
            "country": ["CH", "DE"],
            "created_at": ["2023-06-15 12:00", "2024-01-01 00:00"],
        }
    )


class TestValidData:
    def test_valid_dataframe_passes(
        self, pandera_schema: pa.DataFrameSchema, valid_df: pd.DataFrame
    ):
        result = pandera_schema.validate(valid_df)
        assert len(result) == 2

    def test_nullable_field_accepts_none(
        self, pandera_schema: pa.DataFrameSchema, valid_df: pd.DataFrame
    ):
        valid_df["country"] = [None, "DE"]
        result = pandera_schema.validate(valid_df)
        assert len(result) == 2

    def test_string_numbers_are_coerced(self, pandera_schema: pa.DataFrameSchema):
        df = pd.DataFrame(
            {
                "year": ["2020"],
                "score": ["55.5"],
                "country": ["CH"],
                "created_at": ["2023-06-15 12:00"],
            }
        )
        result = pandera_schema.validate(df)
        assert str(result["year"].dtype) == "Int64"
        assert result["score"].dtype == float


class TestConstraintViolations:
    def test_integer_below_minimum_fails(
        self, pandera_schema: pa.DataFrameSchema, valid_df: pd.DataFrame
    ):
        valid_df["year"] = [1999, 2020]
        with pytest.raises(pa.errors.SchemaError):
            pandera_schema.validate(valid_df)

    def test_number_above_maximum_fails(
        self, pandera_schema: pa.DataFrameSchema, valid_df: pd.DataFrame
    ):
        valid_df["score"] = [50.0, 101.0]
        with pytest.raises(pa.errors.SchemaError):
            pandera_schema.validate(valid_df)

    def test_string_too_short_fails(
        self, pandera_schema: pa.DataFrameSchema, valid_df: pd.DataFrame
    ):
        valid_df["country"] = ["A", "DE"]
        with pytest.raises(pa.errors.SchemaError):
            pandera_schema.validate(valid_df)

    def test_string_too_long_fails(
        self, pandera_schema: pa.DataFrameSchema, valid_df: pd.DataFrame
    ):
        valid_df["country"] = ["ABCD", "DE"]
        with pytest.raises(pa.errors.SchemaError):
            pandera_schema.validate(valid_df)

    def test_datetime_before_minimum_fails(
        self, pandera_schema: pa.DataFrameSchema, valid_df: pd.DataFrame
    ):
        valid_df["created_at"] = ["2022-12-31 23:59", "2024-01-01 00:00"]
        with pytest.raises(pa.errors.SchemaError):
            pandera_schema.validate(valid_df)

    def test_datetime_after_maximum_fails(
        self, pandera_schema: pa.DataFrameSchema, valid_df: pd.DataFrame
    ):
        valid_df["created_at"] = ["2023-06-15 12:00", "2026-01-01 00:00"]
        with pytest.raises(pa.errors.SchemaError):
            pandera_schema.validate(valid_df)


class TestStrictMode:
    def test_extra_column_fails(
        self, pandera_schema: pa.DataFrameSchema, valid_df: pd.DataFrame
    ):
        valid_df["extra"] = ["x", "y"]
        with pytest.raises(pa.errors.SchemaError):
            pandera_schema.validate(valid_df)

    def test_missing_required_column_fails(self, pandera_schema: pa.DataFrameSchema):
        df = pd.DataFrame({"year": [2020], "score": [50.0]})
        with pytest.raises(pa.errors.SchemaError):
            pandera_schema.validate(df)
