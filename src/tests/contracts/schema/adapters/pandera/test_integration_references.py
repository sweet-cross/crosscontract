import pandas as pd
import pytest
from pandera.errors import SchemaError

from crosscontract.contracts.schema import TableSchema
from crosscontract.contracts.schema.adapters import PanderaPandasAdapter
from crosscontract.contracts.schema.fields import IntegerField, StringField
from crosscontract.contracts.schema.reference.foreign_key import (
    ForeignKey,
    ReferencedField,
)
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

    @pytest.mark.parametrize("fk_values", ["asdasdasd", [10, 20]])
    def test_external_wrong_format(self, fk_values, schema):
        df = pd.DataFrame({"id": [2], "parent_id": [10]})
        with pytest.raises(ValueError):
            PanderaPandasAdapter.convert_schema(
                schema, primary_key_values=fk_values
            ).validate(df)


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
        PanderaPandasAdapter.convert_schema(
            fk_schema, foreign_key_values=fk_values
        ).validate(df)

    def test_valid_missing_reference(self, fk_schema):
        """If the referring field is nullable, missing values should pass validation."""
        df = pd.DataFrame({"id": [1, 2], "other_id": [pd.NA, 11]})
        # Key is tuple of referring fields
        fk_values = {("other_id",): [(10,), (11,), (12,)]}
        PanderaPandasAdapter.convert_schema(
            fk_schema, foreign_key_values=fk_values
        ).validate(df)

    def test_invalid_external_fk(self, fk_schema):
        df = pd.DataFrame({"id": [1, 2], "other_id": [10, 99]})
        fk_values = {("other_id",): [(10,), (11,)]}
        with pytest.raises(SchemaError):
            PanderaPandasAdapter.convert_schema(
                fk_schema, foreign_key_values=fk_values
            ).validate(df)

        # but passes if we skip foreign key validation
        PanderaPandasAdapter.convert_schema(
            fk_schema, skip_foreign_key_validation=True
        ).validate(df)

    def test_missing_external_values_raises_value_error(self, fk_schema):
        df = pd.DataFrame({"id": [1], "other_id": [10]})
        with pytest.raises(ValueError, match="Cannot validate foreign key"):
            PanderaPandasAdapter.convert_schema(fk_schema).validate(df)

    def test_empty_external_values_fails_validation(self, fk_schema):
        """An empty referenced table is a validation result, not an inability."""
        df = pd.DataFrame({"id": [1], "other_id": [10]})
        fk_values = {("other_id",): []}
        with pytest.raises(SchemaError):
            PanderaPandasAdapter.convert_schema(
                fk_schema, foreign_key_values=fk_values
            ).validate(df)

    def test_empty_external_values_pass_for_null_rows(self, fk_schema):
        """Null referring values pass even when the referenced table is empty."""
        df = pd.DataFrame({"id": [1], "other_id": [pd.NA]})
        fk_values = {("other_id",): []}
        PanderaPandasAdapter.convert_schema(
            fk_schema, foreign_key_values=fk_values
        ).validate(df)

    def test_empty_external_values_ok_for_self_reference(self, self_ref_schema):
        """A self-reference takes its valid set from the frame, so [] still passes."""
        df = pd.DataFrame({"id": [1, 2], "parent_id": [None, 1]})
        df["parent_id"] = df["parent_id"].astype("Int64")
        fk_values = {("parent_id",): []}
        PanderaPandasAdapter.convert_schema(
            self_ref_schema, foreign_key_values=fk_values
        ).validate(df)

    def test_valid_self_reference(self, self_ref_schema):
        df = pd.DataFrame({"id": [1, 2], "parent_id": [None, 1]})
        # Ensure nullable int
        df["parent_id"] = df["parent_id"].astype("Int64")
        PanderaPandasAdapter.convert_schema(self_ref_schema).validate(df)

    def test_invalid_self_reference(self, self_ref_schema):
        df = pd.DataFrame({"id": [1, 2], "parent_id": [None, 99]})
        df["parent_id"] = df["parent_id"].astype("Int64")
        with pytest.raises(SchemaError):
            PanderaPandasAdapter.convert_schema(self_ref_schema).validate(df)

    def test_self_reference_with_external(self, self_ref_schema):
        # 2 refers to 10 which is external (e.g. from previous batch)
        df = pd.DataFrame({"id": [2], "parent_id": [10]})
        df["parent_id"] = df["parent_id"].astype("Int64")
        fk_values = {("parent_id",): [(10,)]}
        PanderaPandasAdapter.convert_schema(
            self_ref_schema, foreign_key_values=fk_values
        ).validate(df)

    @pytest.mark.parametrize(
        "fk_values",
        [
            {("parent_id",): "not a list of tuples"},  # Wrong type
            {("parent_id",): [10, 20]},  # List of non-tuples
        ],
    )
    def test_external_wrong_format(self, fk_values, self_ref_schema):
        df = pd.DataFrame({"id": [2], "parent_id": [10]})
        with pytest.raises(ValueError):
            PanderaPandasAdapter.convert_schema(
                self_ref_schema, foreign_key_values=fk_values
            ).validate(df)


@pytest.mark.parametrize(
    "given, should_raise",
    [
        # Valid inputs
        (None, False),
        ([(10,), (11,)], False),
        (((10,), (11,)), False),
        ({(10,), (11,)}, False),
        ([(1, 2), (3, 4)], False),
        ([], False),
        # Invalid inputs
        ([10, 11], True),
        ([[10], [11]], True),
        ("not a list", True),
        (123, True),
        ([10, (11,)], True),
        ([(10,), [11]], True),
        ({10, 11}, True),
    ],
)
def test_check_reference_inputs(given, should_raise):
    if should_raise:
        with pytest.raises(ValueError, match="Existing references must be"):
            PanderaPandasAdapter._check_reference_inputs(given)
    else:
        PanderaPandasAdapter._check_reference_inputs(given)
