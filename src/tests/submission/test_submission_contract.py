from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

from crosscontract.contracts import BaseContract
from crosscontract.submission import SubmissionContract

from .conftest import resolver_for, resolver_returning, target_contract

valid_data = {
    "name": "submission1",
    "title": "Test Submission",
    "description": "A test submission contract.",
    "project_name": "project1",
    "replace_key": "all",
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


class TestReplaceKey:
    """The columns identifying the slice a resubmission replaces.

    Required, so the destructive setting is never reached by omission: either a
    list of target columns, or the literal `all` for the whole contract.
    """

    def test_list_of_columns(self):
        """Test that a list of column names is accepted and kept as given."""
        data = deepcopy(valid_data)
        data["replace_key"] = ["model_id", "scenario"]
        contract = SubmissionContract.model_validate(data)
        assert contract.replace_key == ["model_id", "scenario"]

    def test_all_literal(self):
        """Test that the literal `all` is accepted."""
        data = deepcopy(valid_data)
        data["replace_key"] = "all"
        contract = SubmissionContract.model_validate(data)
        assert contract.replace_key == "all"

    def test_missing_is_rejected(self):
        """Test that omitting the field is a validation error rather than a
        default."""
        invalid_data = deepcopy(valid_data)
        del invalid_data["replace_key"]
        with pytest.raises(ValueError, match="replace_key"):
            SubmissionContract.model_validate(invalid_data)

    def test_none_is_rejected(self):
        """Test that an explicit null is rejected — there is no "no key" value."""
        invalid_data = deepcopy(valid_data)
        invalid_data["replace_key"] = None
        with pytest.raises(ValueError, match="replace_key"):
            SubmissionContract.model_validate(invalid_data)

    def test_empty_list_is_rejected(self):
        """Test that an empty list is rejected, so `all` is the only way to say
        "the whole contract"."""
        invalid_data = deepcopy(valid_data)
        invalid_data["replace_key"] = []
        with pytest.raises(ValueError, match="replace_key"):
            SubmissionContract.model_validate(invalid_data)

    def test_duplicate_columns_are_rejected(self):
        """Test that a repeated column name is rejected and named in the error.

        Matched against the phrase rather than the bare column name: pydantic
        echoes the rejected input into the error string, so a bare name matches
        whether or not the message itself names the duplicate.
        """
        invalid_data = deepcopy(valid_data)
        invalid_data["replace_key"] = ["model_id", "scenario", "model_id"]
        with pytest.raises(
            ValueError, match=r"Duplicate replace_key columns: model_id"
        ):
            SubmissionContract.model_validate(invalid_data)

    def test_bare_string_is_rejected(self):
        """Test that a single column name as a string is rejected — only `all` is
        accepted unlisted."""
        invalid_data = deepcopy(valid_data)
        invalid_data["replace_key"] = "model_id"
        with pytest.raises(ValueError, match="replace_key"):
            SubmissionContract.model_validate(invalid_data)

    @pytest.mark.parametrize("replace_key", ["all", ["model_id"], ["model_id", "run"]])
    def test_model_round_trip(self, replace_key):
        """Test that both forms survive a dump and reload."""
        data = deepcopy(valid_data)
        data["replace_key"] = replace_key
        contract = SubmissionContract.model_validate(data)
        reloaded = SubmissionContract.model_validate(contract.model_dump(mode="json"))
        assert reloaded.replace_key == replace_key
        assert reloaded == contract

    @pytest.mark.parametrize("replace_key", ["all", ["model_id"], ["model_id", "run"]])
    def test_server_round_trip(self, replace_key):
        """Test that both forms survive the server payload conversion."""
        data = deepcopy(valid_data)
        data["replace_key"] = replace_key
        contract = SubmissionContract.model_validate(data)
        payload = contract.to_server()
        assert payload["replace_key"] == replace_key
        assert SubmissionContract.from_server(payload) == contract


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


keyed_data = {
    "name": "submission_replace_key",
    "title": "Test Submission",
    "description": "A submission contract whose replace key names columns.",
    "project_name": "project1",
    "replace_key": ["model_id"],
    "tableschema": {
        "fields": [
            {
                "name": "variable",
                "type": "string",
                "constraints": {"required": True},
            },
            {"name": "model_id", "type": "string", "constraints": {"required": True}},
            {"name": "value", "type": "number"},
        ]
    },
    "extraction": {
        "routing_column": "variable",
        "targets": [
            {"name": "t_a", "filters": {"variable": "a"}, "contract": "contract_a"},
            {"name": "t_b", "filters": {"variable": "b"}, "contract": "contract_b"},
        ],
    },
}


def keyed_submission(replace_key: list[str] | str) -> SubmissionContract:
    """Build a submission contract with two targets and the given replace key.

    Args:
        replace_key (list[str] | str): The value for `replace_key`.

    Returns:
        SubmissionContract: The contract, naming `contract_a` and `contract_b`.
    """
    data = deepcopy(keyed_data)
    data["replace_key"] = replace_key
    return SubmissionContract.model_validate(data)


def keyed_target(name: str, *key_columns: str, required: bool = True) -> BaseContract:
    """Build a target contract declaring the given key columns, plus `value`.

    Args:
        name (str): The contract name, matching the target's `contract`.
        *key_columns (str): The replace-key columns the contract declares.
        required (bool, optional): Whether those columns are required.
            Defaults to `True`.

    Returns:
        BaseContract: The contract.
    """
    return target_contract(
        name,
        [
            {"name": column, "type": "string", "constraints": {"required": required}}
            for column in key_columns
        ]
        + [{"name": "value", "type": "number"}],
    )


class TestValidateReferencesReplaceKey:
    """The replace key checked against the contracts the targets name.

    The columns name the target contracts as they land after extraction, so
    they are checked there rather than against the submission's own
    `tableschema`.
    """

    def test_every_target_declares_the_key(self):
        """Test that a key every target declares as required passes."""
        contract = keyed_submission(["model_id"])
        resolver = resolver_for(
            contract_a=keyed_target("contract_a", "model_id"),
            contract_b=keyed_target("contract_b", "model_id"),
        )
        contract.validate_references(resolver)

    def test_all_skips_the_check(self):
        """Test that `all` is not checked against the targets at all."""
        contract = keyed_submission("all")
        resolver = resolver_for(
            contract_a=keyed_target("contract_a"),
            contract_b=keyed_target("contract_b"),
        )
        contract.validate_references(resolver)

    def test_missing_column_is_reported(self):
        """Test that a target whose contract lacks a key column is reported, and
        a target whose contract declares it is not.

        Target names are matched quoted, as the existing error format writes
        them: `contract_a` contains `t_a` as a substring, so a bare name would
        match the contract rather than the target.
        """
        contract = keyed_submission(["model_id"])
        resolver = resolver_for(
            contract_a=keyed_target("contract_a", "model_id"),
            contract_b=keyed_target("contract_b"),
        )
        with pytest.raises(ValueError) as exc_info:
            contract.validate_references(resolver)
        message = str(exc_info.value)
        assert "'t_b'" in message
        assert "model_id" in message
        assert "'t_a'" not in message

    def test_optional_column_is_reported(self):
        """Test that a key column the target contract declares but does not
        require is reported — a null key tuple makes the replace unreliable."""
        contract = keyed_submission(["model_id"])
        resolver = resolver_for(
            contract_a=keyed_target("contract_a", "model_id"),
            contract_b=keyed_target("contract_b", "model_id", required=False),
        )
        with pytest.raises(ValueError) as exc_info:
            contract.validate_references(resolver)
        message = str(exc_info.value)
        assert "'t_b'" in message
        assert "model_id" in message
        assert "'t_a'" not in message

    def test_every_offending_target_is_reported(self):
        """Test that both offending targets appear, rather than only the first."""
        contract = keyed_submission(["model_id"])
        resolver = resolver_for(
            contract_a=keyed_target("contract_a"),
            contract_b=keyed_target("contract_b", "model_id", required=False),
        )
        with pytest.raises(ValueError) as exc_info:
            contract.validate_references(resolver)
        message = str(exc_info.value)
        assert "'t_a'" in message
        assert "'t_b'" in message

    def test_every_offending_column_is_named(self):
        """Test that each offending column of a multi-column key is named."""
        contract = keyed_submission(["model_id", "run"])
        resolver = resolver_for(
            contract_a=keyed_target("contract_a", "model_id", "run"),
            contract_b=keyed_target("contract_b"),
        )
        with pytest.raises(ValueError) as exc_info:
            contract.validate_references(resolver)
        message = str(exc_info.value)
        assert "model_id" in message
        assert "run" in message

    def test_unresolved_target_skips_the_column_check(self):
        """Test that an unresolved contract is reported as unknown only, without
        the column check running against `None`."""
        contract = keyed_submission(["model_id"])
        resolver = resolver_for(
            contract_a=keyed_target("contract_a", "model_id"),
            contract_b=None,
        )
        with pytest.raises(ValueError) as exc_info:
            contract.validate_references(resolver)
        message = str(exc_info.value)
        assert "unknown contract 'contract_b'" in message
        assert "model_id" not in message

    def test_unresolved_and_column_errors_are_reported_together(self):
        """Test that both kinds of error land in the one exception, rather than
        the first raising early."""
        contract = keyed_submission(["model_id"])
        resolver = resolver_for(
            contract_a=None,
            contract_b=keyed_target("contract_b"),
        )
        with pytest.raises(ValueError) as exc_info:
            contract.validate_references(resolver)
        message = str(exc_info.value)
        assert "unknown contract 'contract_a'" in message
        assert "'t_b'" in message
        assert "model_id" in message


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
