import pandas as pd
import pytest
from pandera.errors import SchemaError

from crosscontract.contracts.schema import TableSchema
from crosscontract.contracts.schema.adapters import PanderaPandasAdapter
from crosscontract.contracts.schema.fields import IntegerField, StringField
from crosscontract.contracts.schema.reference.primary_key import PrimaryKey


class TestPrimaryKeyValidation:
    @pytest.fixture
    def schema(self):
        return TableSchema.model_validate(
            {
                "fields": [
                    IntegerField.model_validate({"name": "id"}),
                    StringField.model_validate({"name": "name"}),
                ],
                "primaryKey": PrimaryKey.model_validate("id"),
            }
        )

    def test_valid_pk(self, schema: TableSchema):
        df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        PanderaPandasAdapter.convert_schema(schema).validate(df)

    def test_internal_duplicates(self, schema):
        df = pd.DataFrame({"id": [1, 1, 2], "name": ["a", "b", "c"]})
        # Expect SchemaError (or SchemaErrors if lazy=True)
        with pytest.raises(SchemaError):
            PanderaPandasAdapter.convert_schema(schema).validate(df)

        # but passes if we skip primary key validation
        PanderaPandasAdapter.convert_schema(
            schema, skip_primary_key_validation=True
        ).validate(df)

    def test_external_duplicates(self, schema):
        df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
        existing_pks = [(1,)]
        with pytest.raises(SchemaError):
            PanderaPandasAdapter.convert_schema(
                schema, primary_key_values=existing_pks
            ).validate(df)

    def test_valid_with_external(self, schema):
        df = pd.DataFrame({"id": [2, 3], "name": ["b", "c"]})
        existing_pks = [(1,)]
        PanderaPandasAdapter.convert_schema(
            schema, primary_key_values=existing_pks
        ).validate(df)
