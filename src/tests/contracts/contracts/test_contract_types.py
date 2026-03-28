import pytest
from pydantic import ValidationError

from crosscontract.contracts import CrossContract
from crosscontract.contracts.schema import (
    DimensionSchema,
    TableSchema,
    ValueVariableSchema,
)

data_base_contract = {
    "name": "data_base_contract",
    "title": "Data Base Contract",
    "description": "A base contract for testing contract type differentiation.",
    "tableschema": {
        "fields": [
            {"name": "id", "type": "integer"},
        ],
    },
}


class TestContractTypeDifferentiation:
    """Test suite to ensure CrossContract correctly routes and instantiates
    specialized schemas."""

    @pytest.mark.parametrize(
        "input_type, expected_type, expected_schema_cls",
        [
            (
                None,
                "General",
                TableSchema,
            ),  # Tests the default fallback when key is omitted
            ("Dimension", "Dimension", DimensionSchema),
            ("ValueVariable", "ValueVariable", ValueVariableSchema),
        ],
        ids=["default_general", "dimension", "value_variable"],
    )
    def test_contract_type_resolves_to_correct_schema(
        self, input_type, expected_type, expected_schema_cls
    ):
        """Ensure specific contract types build their corresponding schema classes."""
        data = {**data_base_contract}

        # Only inject if it's not None, to test the default fallback behavior
        if input_type is not None:
            data["contract_type"] = input_type

        contract = CrossContract.model_validate(data)

        assert contract.contract_type == expected_type
        # Use `is` to ensure strict class identity, not just inheritance
        assert type(contract.tableschema) is expected_schema_cls

    def test_invalid_contract_type_raises_validation_error(self):
        """Ensure Pydantic's Literal typing catches unknown contract types."""
        data = {**data_base_contract, "contract_type": "InvalidType"}

        with pytest.raises(ValidationError) as exc_info:
            CrossContract.model_validate(data)

        assert "Input should be 'General', 'Dimension' or 'ValueVariable'" in str(
            exc_info.value
        )

    def test_non_dict_input_raises_type_error(self):
        """Ensure the before validator blocks non-dictionary inputs like ORM objects
        or lists."""
        unsupported_input = ["this", "is", "a", "list"]

        with pytest.raises(
            TypeError,
            match="must be initialized with a dictionary or keyword arguments",
        ):
            CrossContract.model_validate(unsupported_input)

    def test_revalidation_passes_existing_instance(self):
        """Ensure an already built CrossContract bypasses the dict-check gracefully."""
        original_contract = CrossContract.model_validate(data_base_contract)

        revalidated_contract = CrossContract.model_validate(original_contract)

        assert revalidated_contract.name == original_contract.name
        assert type(revalidated_contract.tableschema) is TableSchema


class TestInjectTableTypeToSchema:
    """Test suite for the pure dict-transformation logic of CrossContract schema
    routing."""

    def test_missing_tableschema_raises_value_error(self):
        """Ensure it fails fast if 'tableschema' is entirely missing."""
        input_data = {"contract_type": "Dimension", "name": "my_contract"}

        with pytest.raises(ValueError, match="The 'tableschema' field is required"):
            CrossContract._inject_table_type_to_schema(input_data)

    def test_invalid_tableschema_type_raises_type_error(self):
        """Ensure it fails fast if 'tableschema' is not a dictionary (e.g., a list
        or object)."""
        input_data = {
            "contract_type": "Dimension",
            "tableschema": [
                {"name": "id", "type": "integer"}
            ],  # Invalid: list instead of dict
        }

        with pytest.raises(
            TypeError, match="Expected 'tableschema' to be a dictionary"
        ):
            CrossContract._inject_table_type_to_schema(input_data)

    def test_existing_table_type_raises_value_error(self):
        """Ensure users cannot manually bypass the routing by providing 'table_type'."""
        input_data = {
            "contract_type": "Dimension",
            "tableschema": {"table_type": "Dimension", "fields": []},
        }

        with pytest.raises(
            ValueError, match="Do not define 'table_type' inside the tableschema"
        ):
            CrossContract._inject_table_type_to_schema(input_data)

    def test_successful_injection_with_explicit_contract_type(self):
        """Ensure the 'table_type' is correctly injected when 'contract_type' is
        provided."""
        input_data = {
            "contract_type": "Dimension",
            "tableschema": {"fields": [{"name": "id"}]},
        }

        result = CrossContract._inject_table_type_to_schema(input_data)

        assert result["tableschema"]["table_type"] == "Dimension"
        assert result["contract_type"] == "Dimension"
        # Ensure we didn't accidentally delete other schema data
        assert result["tableschema"]["fields"] == [{"name": "id"}]

    def test_successful_injection_with_default_contract_type(self):
        """Ensure it falls back to 'General' if 'contract_type' is omitted from root."""
        input_data = {"name": "default_contract", "tableschema": {"fields": []}}

        result = CrossContract._inject_table_type_to_schema(input_data)

        assert result["tableschema"]["table_type"] == "General"
        assert result["name"] == "default_contract"
        # Ensure we didn't inject 'contract_type' into the outer dict
        assert "contract_type" not in result

    def test_instantiated_schema_mismatch_raises_value_error(self):
        """Ensure it raises an error if a pre-instantiated schema object does not
        match the contract_type."""
        # TableSchema defaults to table_type "General"
        schema_instance = TableSchema(fields=[{"name": "id", "type": "string"}])

        input_data = {
            "contract_type": "Dimension",
            "tableschema": schema_instance,
        }

        with pytest.raises(
            ValueError,
            match=(
                "Mismatch between contract_type 'Dimension' and tableschema.table_type"
                " 'General'."
            ),
        ):
            CrossContract._inject_table_type_to_schema(input_data)

    def test_instantiated_schema_matching_passes_through(self):
        """Ensure a pre-instantiated schema that matches the contract_type passes
        through unmodified."""
        # TableSchema defaults to table_type "General"
        schema_instance = TableSchema(fields=[{"name": "id", "type": "string"}])

        input_data = {
            "contract_type": "General",
            "tableschema": schema_instance,
        }

        result = CrossContract._inject_table_type_to_schema(input_data)

        # Ensure the schema object was passed through by exact identity
        assert result["tableschema"] is schema_instance
        assert result["contract_type"] == "General"
