import pandas as pd
import pandera.pandas as pa
import pytest
from pandera.errors import SchemaErrors
from sqlalchemy import MetaData

from crosscontract.contracts import TableSchema
from crosscontract.contracts.schema.converter import (
    convert_schema_to_pandera,
    convert_schema_to_sqlalchemy,
)


@pytest.fixture
def sample_schema():
    """Create a sample DataContract for testing."""
    fields = [
        {
            "name": "value",
            "type": "number",
            "constraints": {"required": True, "minimum": 0.0, "maximum": 100.0},
        },
        {
            "name": "year",
            "type": "integer",
            "constraints": {"required": True, "minimum": 2000, "maximum": 2025},
        },
        {
            "name": "country",
            "type": "string",
            "constraints": {"required": False, "maxLength": 6, "minLength": 2},
        },
    ]
    return TableSchema.model_validate({"fields": fields})


class TestPanderaFromSchema:
    """Test class for generating Pandera schemas from DataContract."""

    def test_pandera_creation(self, sample_schema: TableSchema):
        """Test creating a Pandera schema from a contract."""
        pschema = convert_schema_to_pandera(sample_schema, name="test_contract")
        assert isinstance(pschema, pa.DataFrameSchema)
        assert pschema.name == "test_contract"
        assert set(pschema.columns.keys()) == {"value", "year", "country"}

    def test_valid_dataframe(self, sample_schema: TableSchema):
        """Test validating a valid dataframe."""
        pschema = convert_schema_to_pandera(sample_schema, name="test_contract")

        valid_df = pd.DataFrame({"value": [50.0], "year": [2022], "country": ["US"]})
        validated_df = pschema.validate(valid_df)
        assert validated_df.loc[0, "value"] == 50.0
        assert validated_df.loc[0, "year"] == 2022
        assert validated_df.loc[0, "country"] == "US"

    def test_value_below_minimum(self, sample_schema: TableSchema):
        """Test error when value is below minimum."""
        pschema = convert_schema_to_pandera(sample_schema, name="test_contract")

        invalid_df = pd.DataFrame(
            {"value": [-10.0], "year": [2030], "country": ["NoCountryForOldMen"]}
        )

        with pytest.raises(SchemaErrors) as exc_info:
            pschema.validate(invalid_df, lazy=True)
        assert len(exc_info.value.schema_errors) == 3


class TestTableFromSchema:
    """Test class for generating SQLAlchemy tables from DataContract."""

    def test_sqlalchemy_table_creation(self, sample_schema: TableSchema):
        """Test creating a SQLAlchemy table from a contract."""
        metadata = MetaData()
        table_name = "test_contract_table"

        table = convert_schema_to_sqlalchemy(
            sample_schema, metadata=metadata, table_name=table_name
        )

        assert table.name == table_name
        assert len(table.columns) == 4
        column_names = [col.name for col in table.columns]
        assert "value" in column_names
        assert "year" in column_names
        assert "country" in column_names
        assert "_id" in column_names  # Primary key

    def test_sqlalchemy_table_raise_id_conflict(self):
        """Test creating a SQLAlchemy table from a contract."""
        metadata = MetaData()
        table_name = "test_contract_table"
        schema = TableSchema.model_validate(
            {
                "fields": [
                    {"name": "value", "type": "integer"},
                    {"name": "_id", "type": "integer"},  # This should raise an error
                ]
            }
        )

        with pytest.raises(ValueError):
            convert_schema_to_sqlalchemy(
                schema, metadata=metadata, table_name=table_name
            )
