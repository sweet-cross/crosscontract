import pandas as pd
import pytest

from crosscontract.contracts.schema.exceptions.validation_error import (
    SchemaValidationError,
)
from crosscontract.contracts.schema.fields import IntegerField, StringField
from crosscontract.contracts.schema.reference.foreign_key import (
    ForeignKey,
    ReferencedField,
)
from crosscontract.contracts.schema.reference.primary_key import PrimaryKey
from crosscontract.contracts.schema.schema import TableSchema
from crosscontract.contracts.schema.validation.validate_pandas_dataframe import (
    validate_pandas_dataframe,
)


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
        validate_pandas_dataframe(schema, df)

    def test_internal_duplicates(self, schema):
        df = pd.DataFrame({"id": [1, 1, 2], "name": ["a", "b", "c"]})
        # Expect SchemaError (or SchemaErrors if lazy=True)
        with pytest.raises(SchemaValidationError):
            validate_pandas_dataframe(schema, df)

        # but passes if we skip primary key validation
        validate_pandas_dataframe(schema, df, skip_primary_key_validation=True)

    def test_external_duplicates(self, schema):
        df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
        existing_pks = [(1,)]
        with pytest.raises(SchemaValidationError):
            validate_pandas_dataframe(schema, df, primary_key_values=existing_pks)

    def test_valid_with_external(self, schema):
        df = pd.DataFrame({"id": [2, 3], "name": ["b", "c"]})
        existing_pks = [(1,)]
        validate_pandas_dataframe(schema, df, primary_key_values=existing_pks)


class TestForeignKeyValidation:
    @pytest.fixture
    def fk_schema(self):
        return TableSchema(
            fields=[
                IntegerField(name="id"),
                IntegerField(name="other_id"),
            ],
            foreignKeys=[
                ForeignKey(
                    fields=["other_id"],
                    reference=ReferencedField(resource="other_resource", fields=["id"]),
                )
            ],
        )

    @pytest.fixture
    def self_ref_schema(self):
        return TableSchema(
            fields=[
                IntegerField(name="id"),
                IntegerField(name="parent_id"),
            ],
            primaryKey=PrimaryKey(root=["id"]),
            foreignKeys=[
                ForeignKey(
                    fields=["parent_id"],
                    reference=ReferencedField(fields=["id"]),  # Self reference
                )
            ],
        )

    def test_valid_external_fk(self, fk_schema):
        df = pd.DataFrame({"id": [1, 2], "other_id": [10, 11]})
        # Key is tuple of referring fields
        fk_values = {("other_id",): [(10,), (11,), (12,)]}
        validate_pandas_dataframe(fk_schema, df, foreign_key_values=fk_values)

    def test_valid_missing_reference(self, fk_schema):
        """If the referring field is nullable, missing values should pass validation."""
        df = pd.DataFrame({"id": [1, 2], "other_id": [pd.NA, 11]})
        # Key is tuple of referring fields
        fk_values = {("other_id",): [(10,), (11,), (12,)]}
        validate_pandas_dataframe(fk_schema, df, foreign_key_values=fk_values)

    def test_invalid_external_fk(self, fk_schema):
        df = pd.DataFrame({"id": [1, 2], "other_id": [10, 99]})
        fk_values = {("other_id",): [(10,), (11,)]}
        with pytest.raises(SchemaValidationError):
            validate_pandas_dataframe(fk_schema, df, foreign_key_values=fk_values)

        # but passes if we skip foreign key validation
        validate_pandas_dataframe(fk_schema, df, skip_foreign_key_validation=True)

    def test_missing_external_values_raises_value_error(self, fk_schema):
        df = pd.DataFrame({"id": [1], "other_id": [10]})
        with pytest.raises(ValueError, match="Cannot validate foreign key"):
            validate_pandas_dataframe(fk_schema, df)

    def test_valid_self_reference(self, self_ref_schema):
        df = pd.DataFrame({"id": [1, 2], "parent_id": [None, 1]})
        # Ensure nullable int
        df["parent_id"] = df["parent_id"].astype("Int64")
        validate_pandas_dataframe(self_ref_schema, df)

    def test_invalid_self_reference(self, self_ref_schema):
        df = pd.DataFrame({"id": [1, 2], "parent_id": [None, 99]})
        df["parent_id"] = df["parent_id"].astype("Int64")
        with pytest.raises(SchemaValidationError):
            validate_pandas_dataframe(self_ref_schema, df)

    def test_self_reference_with_external(self, self_ref_schema):
        # 2 refers to 10 which is external (e.g. from previous batch)
        df = pd.DataFrame({"id": [2], "parent_id": [10]})
        df["parent_id"] = df["parent_id"].astype("Int64")
        fk_values = {("parent_id",): [(10,)]}
        validate_pandas_dataframe(self_ref_schema, df, foreign_key_values=fk_values)
