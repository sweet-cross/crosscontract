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

# these test TableSchema.validate_dataframe, which forwards the existing values
# to the derivation and hands the resulting pandera schema to the runner. The
# derivation itself is covered in adapters/pandera_pandas/test_adapter.py, on the
# check objects rather than through a DataFrame. What these add is the round
# trip: the checks actually run, and a failure surfaces as SchemaValidationError
# rather than pandera's SchemaError, so the errors are shown to propagate through
# the layers.


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
        schema.validate_dataframe(df)

    def test_invalid_dataframe(self, schema: TableSchema):
        df = pd.DataFrame({"id": [1, 2, "three"], "name": ["a", "b", "c"]})
        with pytest.raises(SchemaValidationError):
            schema.validate_dataframe(df)

    def test_invalid_dataframe_non_lazy(self, schema: TableSchema):
        df = pd.DataFrame({"id": [1, 2, "three"], "name": ["a", "b", 3]})
        with pytest.raises(SchemaValidationError) as exc_info:
            schema.validate_dataframe(df, lazy=False)
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
        schema.validate_dataframe(df)

    def test_internal_duplicates(self, schema):
        df = pd.DataFrame({"id": [1, 1, 2], "name": ["a", "b", "c"]})
        # Expect SchemaError (or SchemaErrors if lazy=True)
        with pytest.raises(SchemaValidationError):
            schema.validate_dataframe(df, primary_key_values=[])

    @pytest.mark.parametrize(
        "ids",
        [
            pytest.param([1, 1, 2], id="duplicate"),
            pytest.param([1, None, 2], id="null"),
        ],
    )
    def test_empty_existing_values_still_check_the_key(self, schema, ids):
        """An empty collection turns the key check on with nothing to compare
        against, so non-nullness and uniqueness within the frame are still
        checked. Only `None` leaves the key unchecked."""
        df = pd.DataFrame({"id": ids, "name": ["a", "b", "c"]})
        with pytest.raises(SchemaValidationError) as exc_info:
            schema.validate_dataframe(df, primary_key_values=[])
        # the primary key rule is what failed, not some other constraint
        reported = {str(error["check"]) for error in exc_info.value.to_list()}
        assert any("primary key" in check for check in reported)

    def test_external_duplicates(self, schema):
        df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
        existing_pks = [(1,)]
        with pytest.raises(SchemaValidationError):
            schema.validate_dataframe(df, primary_key_values=existing_pks)

    def test_valid_with_external(self, schema):
        df = pd.DataFrame({"id": [2, 3], "name": ["b", "c"]})
        existing_pks = [(1,)]
        schema.validate_dataframe(df, primary_key_values=existing_pks)

    def test_invalid_with_external(self, schema):
        df = pd.DataFrame({"id": [1, 3], "name": ["b", "c"]})
        existing_pks = [(1,), (3,)]
        with pytest.raises(SchemaValidationError) as exc_info:
            schema.validate_dataframe(df, primary_key_values=existing_pks)
        error = exc_info.value
        # Expect 1 error for the duplicate '1'
        assert len(error.to_pandas()) == 2

    def _test_non_lazy_validation(self, schema):
        df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
        existing_pks = [(1,), (2,)]
        # eager validation should raise only the first error (the duplicate '1')
        with pytest.raises(SchemaValidationError) as exc_info:
            schema.validate_dataframe(df, primary_key_values=existing_pks, lazy=False)
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
        fk_schema.validate_dataframe(df, foreign_key_values=fk_values)

    def test_valid_missing_reference(self, fk_schema):
        """If the referring field is nullable, missing values should pass validation."""
        df = pd.DataFrame({"id": [1, 2], "other_id": [pd.NA, 11]})
        # Key is tuple of referring fields
        fk_values = {("other_id",): [(10,), (11,), (12,)]}
        fk_schema.validate_dataframe(df, foreign_key_values=fk_values)

    def test_invalid_external_fk(self, fk_schema):
        df = pd.DataFrame({"id": [1, 2], "other_id": [12, 99]})
        fk_values = {("other_id",): [(10,), (11,)]}
        with pytest.raises(SchemaValidationError) as exc_info:
            fk_schema.validate_dataframe(df, foreign_key_values=fk_values)
        error = exc_info.value
        assert len(error.to_pandas()) == 2

        # but passes if we skip foreign key validation
        fk_schema.validate_dataframe(df, foreign_key_values=None)

    def test_missing_external_values_is_not_checked(self, fk_schema):
        """An external reference with no supplied values is not checked, and
        that silence is not an error: the caller chose not to supply them.
        Inverted from the ValueError this used to raise."""
        df = pd.DataFrame({"id": [1], "other_id": [10]})
        fk_schema.validate_dataframe(df)

    def test_empty_external_values_fails_validation(self, fk_schema):
        """An empty referenced table is a validation result, not an inability."""
        df = pd.DataFrame({"id": [1, 2], "other_id": [10, 11]})
        fk_values = {("other_id",): []}
        with pytest.raises(SchemaValidationError) as exc_info:
            fk_schema.validate_dataframe(df, foreign_key_values=fk_values)
        error = exc_info.value
        # Both referring rows fail, and to_list() names them
        assert len(error.to_pandas()) == 2
        assert error.to_list()

    def test_empty_external_values_pass_for_null_rows(self, fk_schema):
        """Null referring values pass even when the referenced table is empty."""
        df = pd.DataFrame({"id": [1], "other_id": [pd.NA]})
        fk_values = {("other_id",): []}
        fk_schema.validate_dataframe(df, foreign_key_values=fk_values)

    def test_empty_external_values_ok_for_self_reference(self, self_ref_schema):
        """A self-reference takes its valid set from the frame, so [] still passes."""
        df = pd.DataFrame({"id": [1, 2], "parent_id": [None, 1]})
        df["parent_id"] = df["parent_id"].astype("Int64")
        fk_values = {("parent_id",): []}
        self_ref_schema.validate_dataframe(df, foreign_key_values=fk_values)

    def test_valid_self_reference(self, self_ref_schema):
        df = pd.DataFrame({"id": [1, 2], "parent_id": [None, 1]})
        # Ensure nullable int
        df["parent_id"] = df["parent_id"].astype("Int64")
        self_ref_schema.validate_dataframe(df)

    def test_invalid_self_reference(self, self_ref_schema):
        df = pd.DataFrame({"id": [1, 2], "parent_id": [None, 99]})
        df["parent_id"] = df["parent_id"].astype("Int64")
        with pytest.raises(SchemaValidationError):
            self_ref_schema.validate_dataframe(
                df, foreign_key_values={("parent_id",): []}
            )

    def test_self_reference_with_external(self, self_ref_schema):
        # 2 refers to 10 which is external (e.g. from previous batch)
        df = pd.DataFrame({"id": [2], "parent_id": [10]})
        df["parent_id"] = df["parent_id"].astype("Int64")
        fk_values = {("parent_id",): [(10,)]}
        self_ref_schema.validate_dataframe(df, foreign_key_values=fk_values)


class TestNoneLeavesTheChecksOut:
    """`None` means "do not check this", distinct from an empty collection."""

    @pytest.fixture
    def pk_schema(self):
        return TableSchema.model_validate(
            {
                "fields": [
                    IntegerField.model_validate({"name": "id"}),
                    StringField.model_validate({"name": "name"}),
                ],
                "primaryKey": PrimaryKey.model_validate("id"),
            }
        )

    @pytest.fixture
    def self_ref_schema(self):
        return TableSchema(
            fields=[IntegerField(name="id"), IntegerField(name="parent_id")],
            primaryKey=PrimaryKey(root=["id"]),
            foreignKeys=[
                ForeignKey(
                    fields=["parent_id"],
                    reference=ReferencedField(fields=["id"]),
                )
            ],
        )

    def test_none_leaves_the_primary_key_unchecked(self, pk_schema: TableSchema):
        """A duplicate key passes when no primary key values are given."""
        df = pd.DataFrame({"id": [1, 1, 2], "name": ["a", "b", "c"]})
        pk_schema.validate_dataframe(df, primary_key_values=None)

    def test_none_leaves_the_foreign_keys_unchecked(self, self_ref_schema: TableSchema):
        """A parent that exists nowhere passes when no foreign key values are
        given, even though the key is self-referencing."""
        df = pd.DataFrame({"id": [1, 2], "parent_id": [None, 99]})
        df["parent_id"] = df["parent_id"].astype("Int64")
        self_ref_schema.validate_dataframe(df, foreign_key_values=None)

    def test_an_empty_dict_still_checks_a_self_reference(
        self, self_ref_schema: TableSchema
    ):
        """An empty dict is not `None`: it turns the foreign key checks on, and a
        self-reference then resolves against the DataFrame's own rows."""
        df = pd.DataFrame({"id": [1, 2], "parent_id": [None, 99]})
        df["parent_id"] = df["parent_id"].astype("Int64")
        with pytest.raises(SchemaValidationError):
            self_ref_schema.validate_dataframe(df, foreign_key_values={})
