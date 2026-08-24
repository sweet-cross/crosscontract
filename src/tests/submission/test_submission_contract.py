from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

from crosscontract.submission import SubmissionContract

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
