import pytest
from pydantic import ValidationError

from crosscontract._standards.frictionless import (
    NumberField,
    StringField,
    TableSchema,
)


class TestFieldTypeInjection:
    """The `_default_field_type` model validator and discriminated dispatch."""

    def test_typeless_field_defaults_to_string(self):
        schema = TableSchema(fields=[{"name": "id"}])
        assert isinstance(schema.fields[0], StringField)
        assert schema.fields[0].type == "string"

    def test_explicit_type_is_preserved(self):
        schema = TableSchema(fields=[{"name": "v", "type": "number"}])
        assert isinstance(schema.fields[0], NumberField)
        assert schema.fields[0].type == "number"

    def test_mixed_fields_dispatch_to_correct_models(self):
        schema = TableSchema(
            fields=[
                {"name": "id"},
                {"name": "v", "type": "number"},
                {"name": "active", "type": "boolean"},
                {"name": "tags", "type": "array"},
                {"name": "ts", "type": "datetime"},
                {"name": "blob", "type": "any"},
            ]
        )
        assert [f.type for f in schema.fields] == [
            "string",
            "number",
            "boolean",
            "array",
            "datetime",
            "any",
        ]

    def test_field_model_instance_passes_through(self):
        # An already-constructed field model must be accepted untouched.
        schema = TableSchema(fields=[StringField(name="id")])
        assert isinstance(schema.fields[0], StringField)
        assert schema.fields[0].name == "id"

    def test_unknown_type_is_rejected(self):
        with pytest.raises(ValidationError):
            TableSchema(fields=[{"name": "x", "type": "geopoint"}])

    def test_non_mapping_input_is_rejected(self):
        # The validator passes non-dict input through untouched; structural
        # validation then rejects it rather than crashing in the validator.
        with pytest.raises(ValidationError):
            TableSchema.model_validate(["not", "a", "mapping"])


class TestPrimaryKeyNormalization:
    """`primaryKey` accepts a string or a list of strings."""

    def test_string_becomes_one_element_list(self):
        schema = TableSchema(fields=[{"name": "id"}], primaryKey="id")
        assert schema.primaryKey == ["id"]

    def test_list_is_unchanged(self):
        schema = TableSchema(
            fields=[{"name": "a"}, {"name": "b"}], primaryKey=["a", "b"]
        )
        assert schema.primaryKey == ["a", "b"]

    def test_defaults_to_empty_list(self):
        schema = TableSchema(fields=[{"name": "id"}])
        assert schema.primaryKey == []


class TestForeignKeyNormalization:
    """`ForeignKey.fields` and `Reference.fields` accept a string or list."""

    def test_foreign_key_fields_string_becomes_list(self):
        schema = TableSchema(
            fields=[{"name": "ref"}],
            foreignKeys=[{"fields": "ref", "reference": {"fields": "id"}}],
        )
        assert schema.foreignKeys[0].fields == ["ref"]

    def test_reference_fields_string_becomes_list(self):
        schema = TableSchema(
            fields=[{"name": "ref"}],
            foreignKeys=[{"fields": "ref", "reference": {"fields": "id"}}],
        )
        assert schema.foreignKeys[0].reference.fields == ["id"]

    def test_list_inputs_are_unchanged(self):
        schema = TableSchema(
            fields=[{"name": "a"}, {"name": "b"}],
            foreignKeys=[
                {
                    "fields": ["a", "b"],
                    "reference": {"resource": "other", "fields": ["x", "y"]},
                }
            ],
        )
        fk = schema.foreignKeys[0]
        assert fk.fields == ["a", "b"]
        assert fk.reference.resource == "other"
        assert fk.reference.fields == ["x", "y"]

    def test_reference_resource_defaults_to_empty_string(self):
        schema = TableSchema(
            fields=[{"name": "ref"}],
            foreignKeys=[{"fields": "ref", "reference": {"fields": "id"}}],
        )
        assert schema.foreignKeys[0].reference.resource == ""


class TestExtraAllowed:
    """`extra="allow"` lets custom Frictionless properties ride through."""

    def test_extra_key_on_field_is_preserved(self):
        schema = TableSchema(
            fields=[
                {"name": "id", "type": "string", "fieldDescriptors": {"unit": "kg"}}
            ]
        )
        dumped = schema.model_dump()
        assert dumped["fields"][0]["fieldDescriptors"] == {"unit": "kg"}

    def test_extra_key_on_schema_is_preserved(self):
        schema = TableSchema(fields=[{"name": "id"}], customProp="x")
        assert schema.model_dump()["customProp"] == "x"


class TestStructuralConstraints:
    """Required/default structural rules of the schema."""

    def test_empty_fields_is_rejected(self):
        with pytest.raises(ValidationError):
            TableSchema(fields=[])

    def test_fields_is_required(self):
        with pytest.raises(ValidationError):
            TableSchema()

    def test_missing_values_default(self):
        schema = TableSchema(fields=[{"name": "id"}])
        assert schema.missingValues == [""]
