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
from crosscontract.contracts.schema.validation import validate_dataframe

# these test the validation logic in validate_dataframe, which uses the
# PanderaPandasAdapter for the actual validation. The tests in
# test_integration_pandera_references.py actually test the same but using the
# adapter directly, so we can be sure that the validation logic in the adapter
# is correct and that the validate_dataframe function correctly integrates with
# it. The difference is that here we raise SchemaValidationError, which is
# the error raised by validate_dataframe, while in the adapter tests we raise
# SchemaError, which is the error raised by Pandera. This way we can also
# ensure that the correct errors are raised and propagated through the layers
# of validation.


class TestSimpleValidation:
    @pytest.fixture
    def schema(self):
        return TableSchema.model_validate(
            {
                "fields": [
                    IntegerField.model_validate({"name": "id"}),
                    StringField.model_validate({"name": "name"}),
                ]
            }
        )

    def test_valid_dataframe(self, schema: TableSchema):
        df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        validate_dataframe(schema, df)

    def test_invalid_dataframe(self, schema: TableSchema):
        df = pd.DataFrame({"id": [1, 2, "three"], "name": ["a", "b", "c"]})
        with pytest.raises(SchemaValidationError):
            validate_dataframe(schema, df)

    def test_invalid_dataframe_non_lazy(self, schema: TableSchema):
        df = pd.DataFrame({"id": [1, 2, "three"], "name": ["a", "b", 3]})
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_dataframe(schema, df, lazy=False)
        error = exc_info.value
        # Expect 2 errors: one for the 'id' column and one for the 'name' column
        assert len(error.to_pandas()) == 1


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
        validate_dataframe(schema, df)

    def test_internal_duplicates(self, schema):
        df = pd.DataFrame({"id": [1, 1, 2], "name": ["a", "b", "c"]})
        # Expect SchemaError (or SchemaErrors if lazy=True)
        with pytest.raises(SchemaValidationError):
            validate_dataframe(schema, df)

        # but passes if we skip primary key validation
        validate_dataframe(schema, df, skip_primary_key_validation=True)

    def test_external_duplicates(self, schema):
        df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
        existing_pks = [(1,)]
        with pytest.raises(SchemaValidationError):
            validate_dataframe(schema, df, primary_key_values=existing_pks)

    def test_valid_with_external(self, schema):
        df = pd.DataFrame({"id": [2, 3], "name": ["b", "c"]})
        existing_pks = [(1,)]
        validate_dataframe(schema, df, primary_key_values=existing_pks)

    def test_invalid_with_external(self, schema):
        df = pd.DataFrame({"id": [1, 3], "name": ["b", "c"]})
        existing_pks = [(1,), (3,)]
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_dataframe(schema, df, primary_key_values=existing_pks)
        error = exc_info.value
        # Expect 1 error for the duplicate '1'
        assert len(error.to_pandas()) == 2

    def _test_non_lazy_validation(self, schema):
        df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        existing_pks = [(1,), (2,)]
        # eager validation should raise only the first error (the duplicate '1')
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_dataframe(schema, df, primary_key_values=existing_pks, lazy=False)
        error = exc_info.value
        assert len(error.to_pandas()) == 1


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
        validate_dataframe(fk_schema, df, foreign_key_values=fk_values)

    def test_valid_missing_reference(self, fk_schema):
        """If the referring field is nullable, missing values should pass validation."""
        df = pd.DataFrame({"id": [1, 2], "other_id": [pd.NA, 11]})
        # Key is tuple of referring fields
        fk_values = {("other_id",): [(10,), (11,), (12,)]}
        validate_dataframe(fk_schema, df, foreign_key_values=fk_values)

    def test_invalid_external_fk(self, fk_schema):
        df = pd.DataFrame({"id": [1, 2], "other_id": [12, 99]})
        fk_values = {("other_id",): [(10,), (11,)]}
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_dataframe(fk_schema, df, foreign_key_values=fk_values)
        error = exc_info.value
        assert len(error.to_pandas()) == 2

        # but passes if we skip foreign key validation
        validate_dataframe(fk_schema, df, skip_foreign_key_validation=True)

    def test_missing_external_values_raises_value_error(self, fk_schema):
        df = pd.DataFrame({"id": [1], "other_id": [10]})
        with pytest.raises(ValueError, match="Cannot validate foreign key"):
            validate_dataframe(fk_schema, df)

    def test_empty_external_values_fails_validation(self, fk_schema):
        """An empty referenced table is a validation result, not an inability."""
        df = pd.DataFrame({"id": [1, 2], "other_id": [10, 11]})
        fk_values = {("other_id",): []}
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_dataframe(fk_schema, df, foreign_key_values=fk_values)
        error = exc_info.value
        # Both referring rows fail, and to_list() names them
        assert len(error.to_pandas()) == 2
        assert error.to_list()

    def test_empty_external_values_pass_for_null_rows(self, fk_schema):
        """Null referring values pass even when the referenced table is empty."""
        df = pd.DataFrame({"id": [1], "other_id": [pd.NA]})
        fk_values = {("other_id",): []}
        validate_dataframe(fk_schema, df, foreign_key_values=fk_values)

    def test_empty_external_values_ok_for_self_reference(self, self_ref_schema):
        """A self-reference takes its valid set from the frame, so [] still passes."""
        df = pd.DataFrame({"id": [1, 2], "parent_id": [None, 1]})
        df["parent_id"] = df["parent_id"].astype("Int64")
        fk_values = {("parent_id",): []}
        validate_dataframe(self_ref_schema, df, foreign_key_values=fk_values)

    def test_valid_self_reference(self, self_ref_schema):
        df = pd.DataFrame({"id": [1, 2], "parent_id": [None, 1]})
        # Ensure nullable int
        df["parent_id"] = df["parent_id"].astype("Int64")
        validate_dataframe(self_ref_schema, df)

    def test_invalid_self_reference(self, self_ref_schema):
        df = pd.DataFrame({"id": [1, 2], "parent_id": [None, 99]})
        df["parent_id"] = df["parent_id"].astype("Int64")
        with pytest.raises(SchemaValidationError):
            validate_dataframe(self_ref_schema, df)

    def test_self_reference_with_external(self, self_ref_schema):
        # 2 refers to 10 which is external (e.g. from previous batch)
        df = pd.DataFrame({"id": [2], "parent_id": [10]})
        df["parent_id"] = df["parent_id"].astype("Int64")
        fk_values = {("parent_id",): [(10,)]}
        validate_dataframe(self_ref_schema, df, foreign_key_values=fk_values)
