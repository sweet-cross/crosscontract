from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
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


coverage_data = {
    "name": "submission2",
    "title": "Test Submission",
    "description": "A submission contract carrying several targets.",
    "project_name": "project1",
    "tableschema": {
        "fields": [
            {
                "name": "variable",
                "type": "string",
                "constraints": {"required": True},
            },
            {"name": "country", "type": "string"},
            {"name": "year", "type": "integer"},
            {"name": "value", "type": "number"},
        ]
    },
    "extraction": {
        "routing_column": "variable",
        "targets": [
            {"name": "t_a", "filters": {"variable": "a"}, "contract": "contract_a"},
            {
                "name": "t_b_ch",
                "filters": {"variable": "b", "country": "CH"},
                "contract": "contract_b",
            },
            {"name": "t_year", "filters": {"year": "2030"}, "contract": "contract_c"},
        ],
    },
}


def bundle(*rows: tuple[str, str, int, float]) -> pd.DataFrame:
    """Build a submission frame with the columns `coverage_data` describes.

    Args:
        *rows (tuple[str, str, int, float]): One tuple per row, holding
            `variable`, `country`, `year` and `value`.

    Returns:
        pd.DataFrame: The frame, with `year` as a nullable integer column so the
            string-form matching is exercised against a typed column.
    """
    return pd.DataFrame(
        list(rows), columns=["variable", "country", "year", "value"]
    ).astype({"year": "Int64"})


class TestUnclaimedRows:
    contract = SubmissionContract.model_validate(coverage_data)

    def test_returns_the_rows_no_target_claims(self):
        """Test that only rows matched by no target are returned, with their
        original index labels."""
        df = bundle(
            ("a", "CH", 2020, 1.0),  # claimed by t_a
            ("b", "CH", 2020, 2.0),  # claimed by t_b_ch
            ("b", "DE", 2020, 3.0),  # unclaimed: country does not match
            ("c", "DE", 2030, 4.0),  # claimed by t_year
            ("c", "DE", 2020, 5.0),  # unclaimed: no target wants it
        )
        unclaimed = self.contract.unclaimed_rows(df)
        assert list(unclaimed.index) == [2, 4]
        assert list(unclaimed["value"]) == [3.0, 5.0]

    def test_all_rows_claimed_returns_an_empty_frame(self):
        """Test that a fully claimed bundle yields an empty frame, not None."""
        df = bundle(("a", "CH", 2020, 1.0), ("b", "CH", 2020, 2.0))
        unclaimed = self.contract.unclaimed_rows(df)
        assert unclaimed.empty
        assert list(unclaimed.columns) == list(df.columns)

    def test_non_routing_typed_column_claims_rows(self):
        """Test that a target constraining only a non-routing integer column
        claims its rows, matched against the column's string form."""
        df = bundle(("c", "DE", 2030, 4.0))
        assert self.contract.unclaimed_rows(df).empty

    def test_filters_are_a_conjunction(self):
        """Test that a row matching one filter entry but not the other is
        unclaimed."""
        df = bundle(("b", "DE", 2020, 3.0))
        assert list(self.contract.unclaimed_rows(df).index) == [0]

    def test_row_claimed_by_two_targets_is_claimed(self):
        """Test that a row matched by more than one target is claimed, since
        overlapping targets are legal."""
        df = bundle(("b", "CH", 2030, 6.0))  # claimed by both t_b_ch and t_year
        assert self.contract.unclaimed_rows(df).empty

    def test_input_frame_is_not_mutated(self):
        """Test that the submitted frame is left untouched."""
        df = bundle(("a", "CH", 2020, 1.0), ("c", "DE", 2020, 5.0))
        before = df.copy()
        self.contract.unclaimed_rows(df)
        pd.testing.assert_frame_equal(df, before)
