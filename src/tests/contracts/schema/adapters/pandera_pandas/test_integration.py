"""Integration tests: a converted schema meeting a DataFrame.

Ported from src/tests/contracts/schema/adapters/pandera/test_integration_pandera.py.
The check classes are covered directly under validation/checks/; what these add is
the assembled schema — coercion, the column constraints the field converters
emit, and strict mode — actually running against data.
"""

import pandas as pd
import pandera.pandas as pa
import pytest

from crosscontract.contracts.schema import TableSchema
from crosscontract.contracts.schema.adapters.pandera_pandas import PanderaAdapter


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
    return PanderaAdapter.convert_schema(schema)


@pytest.fixture
def patterned_schema() -> pa.DataFrameSchema:
    """One optional string field carrying a pattern."""
    fields = [
        {
            "name": "code",
            "type": "string",
            "constraints": {"required": False, "pattern": r"^[A-Z]+$"},
        }
    ]
    schema = TableSchema.model_validate({"fields": fields})
    return PanderaAdapter.convert_schema(schema)


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
        """A field that is not required converts to a nullable column."""
        valid_df["country"] = [None, "DE"]
        result = pandera_schema.validate(valid_df)
        assert len(result) == 2

    def test_string_numbers_are_coerced(self, pandera_schema: pa.DataFrameSchema):
        """The conversion sets coerce=True, so a CSV-shaped frame still lands on
        the declared types."""
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


class TestBlankCells:
    """A blank cell is read as a null, before coercion and the column checks."""

    def test_a_blank_optional_field_passes_as_a_null(
        self, pandera_schema: pa.DataFrameSchema, valid_df: pd.DataFrame
    ):
        """`country` declares minLength 2, which a blank read as a value would
        trip. It comes back as a null."""
        valid_df["country"] = ["", "DE"]
        result = pandera_schema.validate(valid_df)
        assert result["country"].isna().tolist() == [True, False]

    def test_a_blank_optional_field_passes_its_pattern(
        self, patterned_schema: pa.DataFrameSchema
    ):
        """A pattern judges a value, and a blank is not one."""
        result = patterned_schema.validate(pd.DataFrame({"code": ["AB", ""]}))
        assert result["code"].isna().tolist() == [False, True]

    def test_a_pattern_violation_still_fails(
        self, patterned_schema: pa.DataFrameSchema
    ):
        """Only a blank is exempt — the pattern still judges every other value."""
        with pytest.raises(pa.errors.SchemaError):
            patterned_schema.validate(pd.DataFrame({"code": ["ab", ""]}))

    def test_a_blank_required_field_fails(
        self, pandera_schema: pa.DataFrameSchema, valid_df: pd.DataFrame
    ):
        """A required field has no null to mean, so a blank is a violation."""
        valid_df["created_at"] = ["", "2024-01-01 00:00"]
        with pytest.raises(pa.errors.SchemaError):
            pandera_schema.validate(valid_df)

    def test_a_blank_required_string_fails_as_missing(self):
        """A required string keeps its null through coercion, so the blank
        reports as missing rather than as a constraint violation."""
        fields = [{"name": "code", "type": "string", "constraints": {"required": True}}]
        schema = TableSchema.model_validate({"fields": fields})
        with pytest.raises(pa.errors.SchemaError, match="non-nullable"):
            PanderaAdapter.convert_schema(schema).validate(
                pd.DataFrame({"code": ["AB", ""]})
            )

    @pytest.mark.parametrize(
        ("field_type", "value"),
        [
            pytest.param("integer", "2020", id="integer"),
            pytest.param("number", "55.5", id="number"),
        ],
    )
    def test_a_blank_numeric_cell_is_not_a_coercion_error(
        self, field_type: str, value: str
    ):
        """The parse runs before coercion, so a blank in a numeric column lands
        as a null rather than failing to become a number."""
        fields = [
            {"name": "value", "type": field_type, "constraints": {"required": False}}
        ]
        schema = TableSchema.model_validate({"fields": fields})
        result = PanderaAdapter.convert_schema(schema).validate(
            pd.DataFrame({"value": [value, ""]})
        )
        assert result["value"].isna().tolist() == [False, True]


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
        """The conversion sets strict=True, so a column the schema does not
        describe is a failure rather than an ignored extra."""
        valid_df["extra"] = ["x", "y"]
        with pytest.raises(pa.errors.SchemaError):
            pandera_schema.validate(valid_df)

    def test_missing_required_column_fails(self, pandera_schema: pa.DataFrameSchema):
        df = pd.DataFrame({"year": [2020], "score": [50.0]})
        with pytest.raises(pa.errors.SchemaError):
            pandera_schema.validate(df)


class TestKeyChecksAreOptIn:
    """The counterpart to the constraint tests: column constraints always run,
    the key checks only when values are supplied. See ADR 0006."""

    @pytest.fixture
    def keyed_schema(self) -> TableSchema:
        return TableSchema.model_validate(
            {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "name", "type": "string"},
                ],
                "primaryKey": ["id"],
            }
        )

    def test_duplicate_key_passes_without_values(self, keyed_schema: TableSchema):
        """Converted bare, the schema permits duplicate primary keys."""
        df = pd.DataFrame({"id": ["a", "a"], "name": ["x", "y"]})
        result = PanderaAdapter.convert_schema(keyed_schema).validate(df, lazy=True)
        assert len(result) == 2

    def test_duplicate_key_fails_with_an_empty_list(self, keyed_schema: TableSchema):
        """An empty list turns the check on with nothing to compare against."""
        df = pd.DataFrame({"id": ["a", "a"], "name": ["x", "y"]})
        schema = PanderaAdapter.convert_schema(keyed_schema, primary_key_values=[])
        with pytest.raises(pa.errors.SchemaErrors):
            schema.validate(df, lazy=True)
