from unittest.mock import MagicMock

import pandas as pd
import pytest

from crosscontract._standards.frictionless import DataResource
from crosscontract.registry.variables.data_variable import CrossDataVariable
from crosscontract.release.data_package._resolve_resource import (
    build_data_resource,
    fetch_data,
    resolve_resources,
)
from crosscontract.transformations import FetchSpecMixin


class FakeRegistry:
    """Minimal stand-in supporting `registry[contract]` lookup."""

    def __init__(self, variables: dict):
        self._variables = variables

    def __getitem__(self, key):
        return self._variables[key]


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
    def test_csv_path_format_and_profile(
        self, make_resource_spec, make_var_for_contract, contract_factory
    ):
        var = make_var_for_contract(contract_factory.build())
        resource = build_data_resource(make_resource_spec(fmt="csv"), var)

        assert resource.name == "my_resource"
        assert resource.path == ["my_resource.csv"]
        assert resource.format == "csv"
        assert resource.profile == "tabular-data-resource"

    def test_parquet_path_format_and_profile(
        self, make_resource_spec, make_var_for_contract, contract_factory
    ):
        var = make_var_for_contract(contract_factory.build())
        resource = build_data_resource(make_resource_spec(fmt="parquet"), var)

        assert resource.path == ["my_resource.parquet"]
        assert resource.format == "parquet"
        assert resource.profile == "data-resource"

    def test_schema_embedded_and_cross_fields_dropped(
        self, make_resource_spec, make_var_for_contract, contract_factory
    ):
        var = make_var_for_contract(contract_factory.build())
        resource = build_data_resource(make_resource_spec(), var)

        assert resource.table_schema is not None
        dumped = resource.model_dump(by_alias=True)
        assert "schema" in dumped
        assert "tableschema" not in dumped
        assert "contract_type" not in dumped

    def test_spec_field_overrides_contract(
        self, make_resource_spec, make_var_for_contract, contract_factory
    ):
        var = make_var_for_contract(contract_factory.build(title="Contract Title"))
        resource = build_data_resource(make_resource_spec(title="Spec Title"), var)

        assert resource.title == "Spec Title"

    def test_unset_spec_field_inherits_contract(
        self, make_resource_spec, make_var_for_contract, contract_factory
    ):
        contract = contract_factory.build(description="Contract Description")
        var = make_var_for_contract(contract)
        resource = build_data_resource(make_resource_spec(), var)

        assert resource.description == "Contract Description"

    def test_unsupported_format_raises(self, make_resource_spec):
        spec = make_resource_spec()
        # Bypass the Literal["csv", "parquet"] guard to reach the defensive
        # branch (FetchSpecMixin has no validate_assignment).
        spec.data_instructions.fetch.format = "xml"

        with pytest.raises(ValueError, match="Unsupported data format"):
            build_data_resource(spec, MagicMock())


class TestResolveResources:
    def test_returns_mapping_of_resources(self, make_package_spec, make_data_variable):
        df = pd.DataFrame({"id": ["a", "b"]})
        spec = make_package_spec(("res_a", "res_b"))
        registry = FakeRegistry(
            {"res_a": make_data_variable(df), "res_b": make_data_variable(df)}
        )

        result = resolve_resources(registry, spec)

        assert set(result) == {"res_a", "res_b"}
        for name in ("res_a", "res_b"):
            assert isinstance(result[name]["data_resource"], DataResource)
            pd.testing.assert_frame_equal(result[name]["data"], df)

    def test_empty_dataframe_is_warned_and_skipped(
        self, make_package_spec, make_data_variable
    ):
        spec = make_package_spec(("res_a",))
        registry = FakeRegistry({"res_a": make_data_variable(pd.DataFrame())})

        with pytest.warns(UserWarning, match="is empty"):
            result = resolve_resources(registry, spec)

        assert result == {}

    def test_duplicate_resource_name_raises(
        self, make_package_spec, make_resource_spec, make_data_variable
    ):
        df = pd.DataFrame({"id": ["a"]})
        spec = make_package_spec(("dup",))
        # Bypass the spec-level unique check to exercise the runtime guard
        # (a future referenced-dimension feature could reintroduce duplicates).
        spec.resources.append(make_resource_spec(contract="dup"))
        registry = FakeRegistry({"dup": make_data_variable(df)})

        with pytest.raises(ValueError, match="Duplicate resource name"):
            resolve_resources(registry, spec)
