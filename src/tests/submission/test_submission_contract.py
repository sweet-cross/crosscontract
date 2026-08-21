from copy import deepcopy

import pytest

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
        "targets": [{"filters": {"variable": "var1"}, "contract": "contract1"}],
    },
}


class TestSubmissionContract:
    def test_valid_submission_contract(self):
        """Test the creation of a SubmissionContract instance with valid data."""
        submission_contract = SubmissionContract.model_validate(valid_data)
        assert submission_contract.name == "submission1"
        assert submission_contract.project_name == "project1"
        assert submission_contract.extraction.routing_column == "variable"

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

    def test_routing_column_has_enum_constraint(self):
        """Test that a ValidationError is raised when the routing column has an
        enum constraint."""
        invalid_data = deepcopy(valid_data)
        invalid_data["tableschema"]["fields"][0]["constraints"]["enum"] = [
            "var1",
            "var2",
        ]
        with pytest.raises(ValueError, match="cannot have an enum constraint"):
            SubmissionContract.model_validate(invalid_data)

    def test_invalid_filter_in_target(self):
        """Test that a ValidationError is raised when a target has an invalid filter."""
        invalid_data = deepcopy(valid_data)
        invalid_data["extraction"]["targets"][0]["filters"] = {
            "invalid_column": "value"
        }
        with pytest.raises(ValueError, match="Filter columns"):
            SubmissionContract.model_validate(invalid_data)
