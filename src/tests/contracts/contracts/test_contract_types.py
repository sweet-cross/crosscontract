from typing import get_args

import pytest
from pydantic import ValidationError

from crosscontract.contracts import CrossContract
from crosscontract.contracts.contracts.cross_contract import (
    CONTRACT_TYPE_TO_TABLE_TYPE,
    AnyTableSchema,
    ContractType,
    TableType,
)
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


class TestContractTypeToTableTypeMapping:
    """Test suite guarding the contract type to table type table against drift."""

    @staticmethod
    def _schema_discriminator_tags() -> set[str]:
        """Collect the `table_type` tags the schema union actually declares.

        Reads the tags off the schema classes themselves rather than off
        `TableType`, so these tests fail on a mapping that names a table type no
        schema can resolve.

        Returns:
            set[str]: Every discriminator tag `AnyTableSchema` resolves.
        """
        union_members = get_args(get_args(AnyTableSchema)[0])
        return {
            get_args(member.model_fields["table_type"].annotation)[0]
            for member in union_members
        }

    def test_every_contract_type_is_mapped(self):
        """Ensure a newly added contract type cannot ship without a table type."""
        assert set(get_args(ContractType)) == set(CONTRACT_TYPE_TO_TABLE_TYPE)

    def test_every_mapped_table_type_is_resolvable(self):
        """Ensure the mapping only points at table types a schema really declares."""
        assert (
            set(CONTRACT_TYPE_TO_TABLE_TYPE.values())
            <= self._schema_discriminator_tags()
        )

    def test_table_type_literal_matches_the_schema_union(self):
        """Ensure the `TableType` alias does not drift from the schema classes."""
        assert set(get_args(TableType)) == self._schema_discriminator_tags()


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
            ("ValueVariable", "ValueVariable", ValueVariableSchema),
            (
                "Submission",
                "Submission",
                TableSchema,
            ),  # Submission maps to General schema
        ],
        ids=["default_general", "value_variable", "submission"],
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

    def test_contract_type_resolves_to_correct_schema_dimension(self):
        """Ensure specific contract types build their corresponding schema classes."""
        data = {**data_base_contract}
        data["contract_type"] = "Dimension"
        del data["tableschema"]  # Remove tableschema to trigger template injection

        contract = CrossContract.model_validate(data)

        assert contract.contract_type == "Dimension"
        # Use `is` to ensure strict class identity, not just inheritance
        assert type(contract.tableschema) is DimensionSchema

    def test_invalid_contract_type_raises_validation_error(self):
        """Ensure Pydantic's Literal typing catches unknown contract types.

        An unmapped contract type also leaves `tableschema` without its
        discriminator, so pydantic reports a second error against `tableschema`.
        Assert that the `contract_type` error is present, not on the error count.
        """
        data = {**data_base_contract, "contract_type": "InvalidType"}

        with pytest.raises(ValidationError) as exc_info:
            CrossContract.model_validate(data)

        errors = exc_info.value.errors()
        assert any(
            error.get("loc") == ("contract_type",)
            and error.get("type") == "literal_error"
            for error in errors
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

    def test_missing_tableschema_injects_empty_dict(self):
        """Ensure omitting the schema initializes an empty dict and injects routing."""
        input_data = {"contract_type": "Dimension", "name": "my_contract"}

        result = CrossContract._inject_table_type_to_schema(input_data)

        # It should have instantiated an empty dict and injected the table_type
        assert result["tableschema"] == {"table_type": "Dimension"}

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
                "Mismatch between contract_type 'Dimension', which maps to table_type"
                " 'Dimension', and the provided tableschema.table_type 'General'."
            ),
        ):
            CrossContract._inject_table_type_to_schema(input_data)

    def test_instantiated_subclass_schema_mismatch_raises_value_error(self):
        """Ensure a specialized schema is rejected under a contract_type that maps to
        its base schema, not just the other way around."""
        schema_instance = ValueVariableSchema(fields=[{"name": "id", "type": "string"}])

        input_data = {
            "contract_type": "General",
            "tableschema": schema_instance,
        }

        with pytest.raises(
            ValueError,
            match=(
                "Mismatch between contract_type 'General', which maps to table_type"
                " 'General', and the provided tableschema.table_type 'ValueVariable'."
            ),
        ):
            CrossContract._inject_table_type_to_schema(input_data)

    @pytest.mark.parametrize(
        "contract_type",
        ["General", "Submission"],
        ids=["identity_mapping", "non_identity_mapping"],
    )
    def test_instantiated_schema_matching_passes_through(self, contract_type):
        """Ensure a pre-instantiated schema matching the mapped table type passes
        through unmodified.

        Covers both shapes of the mapping: `General` maps onto itself, while
        `Submission` maps onto the `General` table type. The second case is the
        one that breaks if the lookup ever regresses to comparing `contract_type`
        against `table_type` directly.
        """
        # TableSchema defaults to table_type "General"
        schema_instance = TableSchema(fields=[{"name": "id", "type": "string"}])

        input_data = {
            "contract_type": contract_type,
            "tableschema": schema_instance,
        }

        result = CrossContract._inject_table_type_to_schema(input_data)

        # Ensure the schema object was passed through by exact identity
        assert result["tableschema"] is schema_instance
        assert result["contract_type"] == contract_type
