import pytest
from pydantic import ValidationError

from crosscontract.contracts.schema import DimensionSchema

# Assuming your imports look something like this:
# from your_module.schemas import DimensionSchema, DIMENSION_SCHEMA_TEMPLATE


class TestDimensionSchema:
    """Test suite for the rigid DimensionSchema auto-generation and validation."""

    def test_dimension_schema_auto_generates_from_empty_dict(self):
        """Ensure an empty dictionary triggers the template injection."""
        # This simulates what CrossContract passes down when a user omits the schema
        input_data = {"table_type": "Dimension"}

        schema = DimensionSchema.model_validate(input_data)

        assert schema.table_type == "Dimension"
        assert schema.primaryKey.root == ["id"]
        # Verify a specific field from the template made it in
        assert schema.fields[0].name == "id"
        assert schema.fields[0].type == "string"

    def test_dimension_schema_rejects_custom_keys(self):
        """Ensure users cannot override the template with custom fields or metadata."""
        input_data = {
            "table_type": "Dimension",
            "title": "My Custom Dimension",  # Illegal key
            "fields": [{"name": "custom_field", "type": "string"}],  # Illegal key
        }

        with pytest.raises(ValueError, match="DimensionSchema is rigidly defined"):
            DimensionSchema.model_validate(input_data)

    def test_garbage_input_handled_by_pydantic(self):
        """Ensure non-dictionary inputs are passed through to Pydantic's core
        validator."""
        input_data = ["this", "is", "a", "list"]

        # Pydantic will raise a ValidationError because it expects a dict/object,
        # not a list
        with pytest.raises(ValidationError) as exc_info:
            DimensionSchema.model_validate(input_data)

        assert (
            "Input should be a valid dictionary or instance of DimensionSchema"
            in str(exc_info.value)
        )

    def test_instantiated_schema_passes_through(self):
        """Ensure an already built DimensionSchema bypasses the before-validator
        safely."""
        # Build one successfully
        original_schema = DimensionSchema.model_validate({"table_type": "Dimension"})

        # Re-validate the object itself
        revalidated_schema = DimensionSchema.model_validate(original_schema)

        assert revalidated_schema is original_schema
        assert revalidated_schema.primaryKey.root == ["id"]
