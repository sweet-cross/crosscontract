from unittest.mock import MagicMock

import pandas as pd
import pytest

from crosscontract.registry.variables.data_variable import CrossDataVariable
from crosscontract.release.data_package._resolve_resource import (
    build_data_resource,
    fetch_data,
)
from crosscontract.release.data_package.release_specification import (
    CrossDataResourceReleaseSpec,
)
from crosscontract.transformations import FetchSpecMixin


class FakeRegistry:
    """Minimal stand-in supporting `registry[contract]` lookup."""

    def __init__(self, variables: dict):
        self._variables = variables

    def __getitem__(self, key):
        return self._variables[key]


def _resource_spec(
    contract: str = "my_resource", fmt: str = "csv", **overrides
) -> CrossDataResourceReleaseSpec:
    """Build a resource spec (name defaults to its fetch contract)."""
    data = {
        "data_instructions": {"fetch": {"contract": contract, "format": fmt}},
        **overrides,
    }
    return CrossDataResourceReleaseSpec.model_validate(data)


def _var_for_contract(contract) -> MagicMock:
    """A variable mock exposing `contract_resource.contract`."""
    var = MagicMock()
    var.contract_resource.contract = contract
    return var


class TestFetchData:
    def test_contract_not_found_raises_valueerror(self):
        registry = FakeRegistry({})
        with pytest.raises(ValueError, match="not found"):
            fetch_data(registry, FetchSpecMixin(contract="missing"))

    def test_data_variable_uses_get_data(self):
        df = pd.DataFrame({"a": [1, 2]})
        var = MagicMock(spec=CrossDataVariable)
        var.get_data.return_value = df
        registry = FakeRegistry({"c": var})

        out_var, out_df = fetch_data(registry, FetchSpecMixin(contract="c"))

        assert out_var is var
        pd.testing.assert_frame_equal(out_df, df)
        # bare spec → empty filters/aggregation collapse to None
        var.get_data.assert_called_once_with(filters=None, aggregation=None)

    def test_non_data_variable_uses_data_attr(self):
        df = pd.DataFrame({"a": [1]})
        var = MagicMock()  # not a CrossDataVariable
        var.data = df
        registry = FakeRegistry({"c": var})

        out_var, out_df = fetch_data(registry, FetchSpecMixin(contract="c"))

        assert out_var is var
        pd.testing.assert_frame_equal(out_df, df)
        var.get_data.assert_not_called()

    def test_get_data_error_wrapped_as_runtimeerror(self):
        var = MagicMock(spec=CrossDataVariable)
        var.get_data.side_effect = KeyError("bad column")
        registry = FakeRegistry({"c": var})

        with pytest.raises(RuntimeError, match="Error fetching data"):
            fetch_data(registry, FetchSpecMixin(contract="c"))


class TestBuildDataResource:
    def test_csv_path_format_and_profile(self, contract_factory):
        contract = contract_factory.build()
        resource = build_data_resource(
            _resource_spec(fmt="csv"), _var_for_contract(contract)
        )

        assert resource.name == "my_resource"
        assert resource.path == ["my_resource.csv"]
        assert resource.format == "csv"
        assert resource.profile == "tabular-data-resource"

    def test_parquet_path_format_and_profile(self, contract_factory):
        contract = contract_factory.build()
        resource = build_data_resource(
            _resource_spec(fmt="parquet"), _var_for_contract(contract)
        )

        assert resource.path == ["my_resource.parquet"]
        assert resource.format == "parquet"
        assert resource.profile == "data-resource"

    def test_schema_embedded_and_cross_fields_dropped(self, contract_factory):
        contract = contract_factory.build()
        resource = build_data_resource(_resource_spec(), _var_for_contract(contract))

        assert resource.table_schema is not None
        dumped = resource.model_dump(by_alias=True)
        assert "schema" in dumped
        assert "tableschema" not in dumped
        assert "contract_type" not in dumped

    def test_spec_field_overrides_contract(self, contract_factory):
        contract = contract_factory.build(title="Contract Title")
        spec = _resource_spec(title="Spec Title")

        resource = build_data_resource(spec, _var_for_contract(contract))

        assert resource.title == "Spec Title"

    def test_unset_spec_field_inherits_contract(self, contract_factory):
        contract = contract_factory.build(description="Contract Description")
        spec = _resource_spec()  # description left unset

        resource = build_data_resource(spec, _var_for_contract(contract))

        assert resource.description == "Contract Description"

    def test_unsupported_format_raises(self):
        spec = _resource_spec()
        # Bypass the Literal["csv", "parquet"] guard to reach the defensive
        # branch (FetchSpecMixin has no validate_assignment).
        spec.data_instructions.fetch.format = "xml"

        with pytest.raises(ValueError, match="Unsupported data format"):
            build_data_resource(spec, MagicMock())
