from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

from crosscontract.contracts import BaseContract
from crosscontract.submission import SubmissionContract

from .conftest import resolver_for, resolver_returning

valid_data = {
    "name": "submission1",
    "title": "Test Submission",
    "description": "A test submission contract.",
    "project_name": "project1",
    "tableschema": {
        "fields": [
            {
                "name": "variable",
                "type": "string",
                "constraints": {"required": True},
            },
            {"name": "value", "type": "number"},
        ]
    },
    "extraction": {
        "routing_column": "variable",
        "targets": [
            {
                "name": "target1",
                "filters": {"variable": "var1"},
                "contract": "contract1",
            }
        ],
    },
}


class TestSubmissionContract:
    def test_valid_submission_contract(self):
        """Test the creation of a SubmissionContract instance with valid data."""
        submission_contract = SubmissionContract.model_validate(valid_data)
        assert submission_contract.name == "submission1"
        assert submission_contract.project_name == "project1"
        assert submission_contract.extraction.routing_column == "variable"
        assert submission_contract.contract_type == "Submission"
        assert submission_contract.tableschema.table_type == "General"

    def test_routing_column_does_not_exist(self):
        """Test that a ValidationError is raised when the routing column is invalid."""
        invalid_data = deepcopy(valid_data)
        invalid_data["extraction"]["routing_column"] = "invalid_column"
        with pytest.raises(ValueError, match="does not exist in the tableschema"):
            SubmissionContract.model_validate(invalid_data)

    def test_routing_column_not_required(self):
        """Test that a ValidationError is raised when the routing column is not
        required."""
        invalid_data = deepcopy(valid_data)
        invalid_data["tableschema"]["fields"][0]["constraints"]["required"] = False
        with pytest.raises(ValueError, match="must be required"):
            SubmissionContract.model_validate(invalid_data)

    def test_routing_column_not_string(self):
        """Test that a ValidationError is raised when the routing column is not a
        string."""
        invalid_data = deepcopy(valid_data)
        invalid_data["tableschema"]["fields"][0]["type"] = "number"
        with pytest.raises(ValueError, match="must be a string column"):
            SubmissionContract.model_validate(invalid_data)

    def test_routing_column_may_have_enum_constraint(self):
        """Test enum is allowed for the submission contract."""
        data = deepcopy(valid_data)
        data["tableschema"]["fields"][0]["constraints"]["enum"] = [
            "var1",
            "var2",
        ]
        spec = SubmissionContract.model_validate(data)
        assert spec.tableschema.fields[0].constraints.enum == ["var1", "var2"]

    def test_invalid_filter_in_target(self):
        """Test that a ValidationError is raised when a target has an invalid filter."""
        invalid_data = deepcopy(valid_data)
        invalid_data["extraction"]["targets"][0]["filters"] = {
            "invalid_column": "value"
        }
        with pytest.raises(ValueError, match="Filter columns"):
            SubmissionContract.model_validate(invalid_data)

    def test_primary_key_not_allowed(self):
        """Test that a ValidationError is raised when the tableschema declares a
        primary key."""
        invalid_data = deepcopy(valid_data)
        invalid_data["tableschema"]["primaryKey"] = ["variable"]
        with pytest.raises(ValueError, match="must not have primary keys"):
            SubmissionContract.model_validate(invalid_data)

    def test_foreign_keys_not_allowed(self):
        """Test that a ValidationError is raised when the tableschema declares a
        foreign key."""
        invalid_data = deepcopy(valid_data)
        invalid_data["tableschema"]["foreignKeys"] = [
            {
                "fields": "variable",
                "reference": {"resource": "dim_variable", "fields": "id"},
            }
        ]
        with pytest.raises(ValueError, match="must not have foreign keys"):
            SubmissionContract.model_validate(invalid_data)


class TestValidateReferences:
    """The contracts the targets name, resolved by name without reading data."""

    def test_all_targets_resolve(
        self,
        contract: SubmissionContract,
        contract_a: BaseContract,
        contract_c: BaseContract,
    ):
        """Test that each target's contract is looked up by its name."""
        resolver = resolver_for(contract_a=contract_a, contract_c=contract_c)
        contract.validate_references(resolver)
        assert [c.args for c in resolver.resolve.call_args_list] == [
            ("contract_a",),
            ("contract_c",),
        ]
        resolver.get_data.assert_not_called()

    def test_one_unresolved_target_raises(
        self, contract: SubmissionContract, contract_a: BaseContract
    ):
        resolver = resolver_for(contract_a=contract_a, contract_c=None)
        with pytest.raises(ValueError) as exc_info:
            contract.validate_references(resolver)
        message = str(exc_info.value)
        assert "contract_c" in message
        assert "contract_a" not in message

    def test_all_unresolved_targets_are_reported_together(
        self, contract: SubmissionContract
    ):
        resolver = resolver_returning(None)
        with pytest.raises(ValueError) as exc_info:
            contract.validate_references(resolver)
        message = str(exc_info.value)
        assert "contract_a" in message
        assert "contract_c" in message

    def test_resolver_error_propagates(self, contract: SubmissionContract):
        resolver = resolver_returning(None)
        resolver.resolve.side_effect = ConnectionError("unreachable")
        with pytest.raises(ConnectionError):
            contract.validate_references(resolver)

    @pytest.mark.parametrize("enforce_star_schema", [True, False])
    def test_enforce_star_schema_has_no_effect(
        self,
        contract: SubmissionContract,
        contract_a: BaseContract,
        contract_c: BaseContract,
        enforce_star_schema: bool,
    ):
        """Test that non-dimension target contracts pass either way."""
        resolver = resolver_for(contract_a=contract_a, contract_c=contract_c)
        contract.validate_references(resolver, enforce_star_schema=enforce_star_schema)


class TestRoundTrip:
    fn_yaml = Path(__file__).parent / "example_submission.yaml"

    def test_yaml_round_trip(self):
        """Test that a SubmissionContract can be serialized to YAML and then
        deserialized back to an equivalent object."""
        read_spec = SubmissionContract.from_file(self.fn_yaml)
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "spec.yaml"
            tmp_path.write_text(
                yaml.safe_dump(read_spec.model_dump(mode="json"), sort_keys=False)
            )
            deserialized_spec = SubmissionContract.from_file(tmp_path)
        assert read_spec == deserialized_spec

    def test_json_round_trip(self):
        """Test that a SubmissionContract can be serialized to JSON and then
        deserialized back to an equivalent object."""
        read_spec = SubmissionContract.from_file(self.fn_yaml)
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "spec.json"
            tmp_path.write_text(read_spec.model_dump_json(indent=2))
            deserialized_spec = SubmissionContract.from_file(tmp_path)
        assert read_spec == deserialized_spec
