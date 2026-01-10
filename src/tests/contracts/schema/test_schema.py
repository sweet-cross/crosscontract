import json

import pandas as pd
import pytest
import yaml
from sqlalchemy import MetaData, Table

from crosscontract.contracts import TableSchema
from crosscontract.contracts.schema.fields import IntegerField, NumberField, StringField

field_data = [
    {"name": "id", "type": "integer"},
    {"name": "name", "type": "string"},
    {"name": "ref_id", "type": "integer"},
]


@pytest.fixture
def sample_schema():
    """Create a sample DataContract for testing."""
    return TableSchema.model_validate(
        {
            "fields": [
                {"name": "field_one", "type": "string"},
                {"name": "field_two", "type": "integer"},
                {"name": "field_three", "type": "number"},
            ]
        }
    )


class TestSchema:
    """Test class for Schema methods."""

    def test_get_existing_field(self, sample_schema: TableSchema):
        """Test retrieving an existing field by name."""
        field = sample_schema.get("field_one")
        assert field is not None
        assert field.name == "field_one"
        assert field.type == "string"
        assert len(sample_schema) == 3

    def test_get_nonexistent_field(self, sample_schema: TableSchema):
        """Test retrieving a non-existent field by name."""
        field = sample_schema.get("nonexistent_field")
        assert field is None

    def test_get_existing_field_assessor(self, sample_schema: TableSchema):
        """Test retrieving an existing field by name."""
        assert sample_schema["field_two"].name == "field_two"
        assert sample_schema[1].type == "integer"
        with pytest.raises(KeyError):
            sample_schema["nonexistent_field"]

    def test_iteration(self, sample_schema: TableSchema):
        """Test iterating over the schema fields."""
        field_names = [field.name for field in sample_schema]
        assert field_names == ["field_one", "field_two", "field_three"]

    def test_field_types(self, sample_schema: TableSchema):
        """Test that the field types are as expected."""
        expected_types = [StringField, IntegerField, NumberField]
        for field, expected_type in zip(sample_schema, expected_types, strict=False):
            assert isinstance(field, expected_type)


class TestFieldNames:
    """Test class for Schema.has_fields method."""

    def test_has_fields_string_success(self, sample_schema: TableSchema):
        """Test has_fields with field_names as string - successful case."""
        assert sample_schema.has_fields("field_one") is True
        assert sample_schema.has_fields("field_two") is True
        assert sample_schema.has_fields("field_three") is True

    def test_has_fields_list_success(self, sample_schema: TableSchema):
        """Test has_fields with field_names as list of strings -
        successful case."""
        assert sample_schema.has_fields(["field_one", "field_two"]) is True
        assert (
            sample_schema.has_fields(["field_one", "field_two", "field_three"]) is True
        )
        assert sample_schema.has_fields(["field_three"]) is True

    def test_has_fields_list_failure(self, sample_schema: TableSchema):
        """Test has_fields with field_names as list -
        failure case when one field doesn't exist."""
        assert sample_schema.has_fields(["field_one", "nonexistent_field"]) is False
        assert sample_schema.has_fields(["nonexistent_field", "field_two"]) is False
        assert sample_schema.has_fields(["nonexistent_field"]) is False


class TestValidation:
    def test_valid_structure(self):
        contract = TableSchema.model_validate(
            {
                "primaryKey": ["id"],
                "foreignKeys": [
                    {
                        "fields": ["ref_id"],
                        "reference": {"resource": None, "fields": ["id"]},
                    }
                ],
                "fieldDescriptors": [
                    {"type": "value", "field": "id", "unit": "units"},
                    {"type": "location", "field": "ref_id", "locationType": "country"},
                ],
                "fields": field_data,
            }
        )

        assert contract.primaryKey is not None
        assert contract.foreignKeys is not None

    def test_valid_only_fields(self):
        contract = TableSchema.model_validate(
            {
                "fieldDescriptors": [
                    {"type": "value", "field": "id", "unit": "units"},
                    {"type": "location", "field": "ref_id", "locationType": "country"},
                ],
                "fields": field_data,
            }
        )
        assert not contract.primaryKey
        assert not contract.foreignKeys

    def test_invalid_primary_key(self):
        with pytest.raises(
            ValueError,
            match="['invalid_id']",
        ):
            TableSchema.model_validate(
                {
                    "primaryKey": ["invalid_id"],
                    "fields": field_data,
                }
            )

    def test_invalid_foreign_key(self):
        with pytest.raises(
            ValueError,
            match="['invalid_id']",
        ):
            TableSchema.model_validate(
                {
                    "foreignKeys": [
                        {
                            "fields": ["invalid_id"],
                            "reference": {"resource": None, "fields": ["id"]},
                        }
                    ],
                    "fields": field_data,
                }
            )

    def test_invalid_self_reference(self):
        with pytest.raises(
            ValueError,
            match="['invalid_id']",
        ):
            TableSchema.model_validate(
                {
                    "foreignKeys": [
                        {
                            "fields": ["ref_id"],
                            "reference": {"resource": None, "fields": ["invalid_id"]},
                        }
                    ],
                    "fields": field_data,
                }
            )

    def test_invalid_field_descriptors(self):
        with pytest.raises(
            ValueError,
            match="Field 'non_existent_field' referenced in descriptor",
        ):
            TableSchema.model_validate(
                {
                    "fieldDescriptors": [
                        {
                            "type": "value",
                            "field": "non_existent_field",
                            "unit": "units",
                        }
                    ],
                    "fields": field_data,
                }
            )


class TestToSaTable:
    def test_to_sa_table(self):
        contract = TableSchema.model_validate(
            {
                "primaryKey": ["id"],
                "fields": field_data,
            }
        )

        metadata = MetaData()
        table = contract.to_sa_table(
            table_name="test_table",
            metadata=metadata,
        )

        assert isinstance(table, Table)
        assert "id" in table.c
        assert "name" in table.c
        assert "ref_id" in table.c
        assert table.name == "test_table"
        assert table.primary_key.columns.keys() == ["_id"]

    def test_to_sa_table_defaults(self):
        contract = TableSchema.model_validate(
            {
                "primaryKey": ["id"],
                "fields": field_data,
            }
        )

        table = contract.to_sa_table()

        assert isinstance(table, Table)
        assert "id" in table.c
        assert "name" in table.c
        assert "ref_id" in table.c
        assert table.name == "dct_contract_table"
        assert table.primary_key.columns.keys() == ["_id"]


class TestToPanderaSchema:
    def test_valid_no_reference(self):
        contract = TableSchema.model_validate({"fields": field_data})

        pandera_schema = contract.to_pandera_schema(name="TestPanderaSchema")

        assert pandera_schema.name == "TestPanderaSchema"
        assert "id" in pandera_schema.columns
        assert "name" in pandera_schema.columns
        assert "ref_id" in pandera_schema.columns

    def test_valid_no_reference_default_name(self):
        contract = TableSchema.model_validate({"fields": field_data})

        pandera_schema = contract.to_pandera_schema()

        assert pandera_schema.name == "contract_schema"
        assert "id" in pandera_schema.columns
        assert "name" in pandera_schema.columns
        assert "ref_id" in pandera_schema.columns


class TestToPydanticModel:
    def test_to_pydantic_model_default_base(self):
        contract = TableSchema.model_validate({"fields": field_data})

        PydanticModel = contract.to_pydantic_model(model_name="TestPydanticModel")

        assert PydanticModel.__name__ == "TestPydanticModel"
        instance = PydanticModel(id=1, name="A", ref_id=2)
        assert instance.id == 1
        assert instance.name == "A"
        assert instance.ref_id == 2

    def test_to_pydantic_model_custom_base(self):
        from pydantic import BaseModel

        class CustomBaseModel(BaseModel):
            class Config:
                arbitrary_types_allowed = True

        contract = TableSchema.model_validate({"fields": field_data})

        PydanticModel = contract.to_pydantic_model(base_class=CustomBaseModel)

        assert PydanticModel.__name__ == "ContractModel"
        assert issubclass(PydanticModel, CustomBaseModel)
        instance = PydanticModel(id=1, name="A", ref_id=2)
        assert instance.id == 1
        assert instance.name == "A"
        assert instance.ref_id == 2


class TestFromFile:
    def test_from_json(self, tmp_path):
        contract_data = {"fields": field_data}
        file_path = tmp_path / "contract.json"
        file_path.write_text(json.dumps(contract_data))

        contract = TableSchema.from_file(str(file_path))

        assert len(contract.fields) == len(field_data)
        for i in range(len(field_data)):
            assert contract.fields[i].name == field_data[i]["name"]

    @pytest.mark.parametrize("ext", ["yaml", "yml"])
    def test_from_yaml(self, tmp_path, ext):
        contract_data = {"fields": field_data}
        file_path = tmp_path / f"contract.{ext}"
        file_path.write_text(yaml.dump(contract_data))

        contract = TableSchema.from_file(str(file_path))

        assert len(contract.fields) == len(field_data)
        for i in range(len(field_data)):
            assert contract.fields[i].name == field_data[i]["name"]


class TestValidateDataFrame:
    def test_valid(self, sample_schema: TableSchema):
        df = pd.DataFrame(
            {
                "field_one": ["a", "b", "c"],
                "field_two": [1, 2, 3],
                "field_three": [1.1, 2.2, 3.3],
            }
        )
        sample_schema.validate_dataframe(df)

    def test_wrong_backend(self, sample_schema: TableSchema):
        df = pd.DataFrame(
            {
                "field_one": ["a", "b", "c"],
                "field_two": [1, 2, 3],
                "field_three": [1.1, 2.2, 3.3],
            }
        )
        with pytest.raises(ValueError):
            sample_schema.validate_dataframe(df, backend="polars")  # type: ignore
