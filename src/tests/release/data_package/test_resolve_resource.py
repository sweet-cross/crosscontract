import warnings
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from crosscontract._standards.frictionless import DataResource
from crosscontract.registry.variables.data_variable import CrossDataVariable
from crosscontract.release.data_package._resolve_resource import (
    _drop_dangling_foreign_keys,
    _filter_pruned_dimensions,
    build_data_resource,
    collect_referenced_resources,
    fetch_data,
    resolve_resources,
)
from crosscontract.transformations import FetchSpecMixin


def _fk(resource, fields=("x",), ref_fields=("x",)):
    """Minimal foreign-key stand-in exposing the attributes
    `collect_referenced_resources` reads (`reference.resource`).
    """
    return SimpleNamespace(
        fields=list(fields),
        reference=SimpleNamespace(resource=resource, fields=list(ref_fields)),
    )


def _fact_contract_with_fk(contract_factory, target="dim_region"):
    """Build a General contract whose schema carries a foreign key to `target`."""
    return contract_factory.build(
        tableschema={
            "fields": [{"name": "region", "type": "string"}],
            "foreignKeys": [
                {
                    "fields": ["region"],
                    "reference": {"resource": target, "fields": ["id"]},
                }
            ],
        },
    )


def _res(name, df, foreign_keys=None):
    """Build a `my_resources` entry (DataResource + data) from a DataFrame.

    Schema fields are derived from the DataFrame columns; `foreign_keys` are
    embedded as-is (dicts in Frictionless form).
    """
    return {
        "data_resource": DataResource(
            name=name,
            path=[f"{name}.csv"],
            table_schema={
                "fields": [{"name": c, "type": "string"} for c in df.columns],
                "foreignKeys": foreign_keys or [],
            },
        ),
        "data": df,
    }


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


class TestCollectReferencedResources:
    def test_collects_referenced_dimension(self, make_data_variable, make_dimension):
        dim = make_dimension(pd.DataFrame({"id": ["a"]}))
        fact = make_data_variable(pd.DataFrame({"region": ["a"]}))
        fact.foreign_keys = [_fk("dim_region")]
        registry = FakeRegistry({"dim_region": dim})

        assert collect_referenced_resources(registry, [fact]) == {"dim_region": dim}

    def test_deduplicated_across_variables(self, make_data_variable, make_dimension):
        dim = make_dimension(pd.DataFrame({"id": ["a"]}))
        fact_a = make_data_variable(pd.DataFrame({"region": ["a"]}))
        fact_a.foreign_keys = [_fk("dim_region")]
        fact_b = make_data_variable(pd.DataFrame({"region": ["b"]}))
        fact_b.foreign_keys = [_fk("dim_region")]
        registry = FakeRegistry({"dim_region": dim})

        assert collect_referenced_resources(registry, [fact_a, fact_b]) == {
            "dim_region": dim
        }

    def test_composite_foreign_key_resolved(self, make_data_variable, make_dimension):
        # A composite-key dimension is absent from `var.dimensions` but is still
        # reachable via `foreign_keys`, which is what this collector uses.
        dim = make_dimension(pd.DataFrame({"a": ["x"], "b": ["y"], "c": ["z"]}))
        fact = make_data_variable(pd.DataFrame({"a": ["x"], "b": ["y"], "c": ["z"]}))
        fact.foreign_keys = [
            _fk("dim_scenario", fields=("a", "b", "c"), ref_fields=("a", "b", "c"))
        ]
        registry = FakeRegistry({"dim_scenario": dim})

        assert collect_referenced_resources(registry, [fact]) == {"dim_scenario": dim}

    def test_self_reference_skipped(self, make_data_variable):
        fact = make_data_variable(pd.DataFrame({"id": ["a"]}))
        fact.foreign_keys = [_fk(None)]
        registry = FakeRegistry({})

        assert collect_referenced_resources(registry, [fact]) == {}

    def test_non_dimension_target_collected(self, make_data_variable):
        # Not restricted to dimensions: any referenced resource is bundled so the
        # package stays self-contained even if the star-schema rule is relaxed.
        other = make_data_variable(pd.DataFrame({"id": ["a"]}))  # not a dimension
        fact = make_data_variable(pd.DataFrame({"x": ["a"]}))
        fact.foreign_keys = [_fk("other")]
        registry = FakeRegistry({"other": other})

        assert collect_referenced_resources(registry, [fact]) == {"other": other}

    def test_unknown_reference_raises_valueerror(self, make_data_variable):
        fact = make_data_variable(pd.DataFrame({"region": ["a"]}))
        fact.foreign_keys = [_fk("missing")]
        registry = FakeRegistry({})  # "missing" not registered

        with pytest.raises(ValueError, match="Referenced contract 'missing' not found"):
            collect_referenced_resources(registry, [fact])


class TestDropDanglingForeignKeys:
    @staticmethod
    def _resource(name, foreign_keys):
        return DataResource(
            name=name,
            path=[f"{name}.csv"],
            table_schema={
                "fields": [{"name": "region", "type": "string"}],
                "foreignKeys": foreign_keys,
            },
        )

    def test_keeps_foreign_key_to_present_target(self):
        fact = self._resource(
            "fact",
            [
                {
                    "fields": ["region"],
                    "reference": {"resource": "dim", "fields": ["id"]},
                }
            ],
        )
        resources = {
            "fact": {"data_resource": fact},
            "dim": {"data_resource": self._resource("dim", [])},
        }

        _drop_dangling_foreign_keys(resources)

        assert len(fact.table_schema.foreignKeys) == 1

    def test_keeps_self_reference(self):
        # An empty `resource` is a self-reference and must survive pruning.
        dim = self._resource(
            "dim",
            [
                {
                    "fields": ["region"],
                    "reference": {"resource": "", "fields": ["region"]},
                }
            ],
        )
        resources = {"dim": {"data_resource": dim}}

        _drop_dangling_foreign_keys(resources)

        assert len(dim.table_schema.foreignKeys) == 1

    def test_drops_dangling_and_warns_by_default(self):
        fact = self._resource(
            "fact",
            [
                {
                    "fields": ["region"],
                    "reference": {"resource": "dim", "fields": ["id"]},
                }
            ],
        )
        resources = {"fact": {"data_resource": fact}}

        with pytest.warns(UserWarning, match="Dropping foreign keys"):
            _drop_dangling_foreign_keys(resources)

        assert fact.table_schema.foreignKeys == []

    def test_warn_false_suppresses_warning(self):
        fact = self._resource(
            "fact",
            [
                {
                    "fields": ["region"],
                    "reference": {"resource": "dim", "fields": ["id"]},
                }
            ],
        )
        resources = {"fact": {"data_resource": fact}}

        with warnings.catch_warnings():
            warnings.simplefilter("error")  # any warning would fail the test
            _drop_dangling_foreign_keys(resources, warn=False)

        assert fact.table_schema.foreignKeys == []


class TestFilterPrunedDimensions:
    _MODEL_FK = [
        {"fields": ["model"], "reference": {"resource": "dim_model", "fields": ["id"]}}
    ]
    _SCENARIO_FK = [
        {
            "fields": ["sg", "sn", "sv"],
            "reference": {
                "resource": "dim_scenario",
                "fields": ["scenario_group", "scenario_name", "scenario_variant"],
            },
        }
    ]

    def test_filters_single_key_dimension(self):
        fact = _res(
            "fact",
            pd.DataFrame({"model": ["a", "b"], "value": ["1", "2"]}),
            foreign_keys=self._MODEL_FK,
        )
        dim = _res(
            "dim_model", pd.DataFrame({"id": ["a", "b", "c"], "label": list("ABC")})
        )
        resources = {"fact": fact, "dim_model": dim}

        _filter_pruned_dimensions(resources)

        assert sorted(resources["dim_model"]["data"]["id"]) == ["a", "b"]

    def test_filters_composite_key_dimension(self):
        fact = _res(
            "fact",
            pd.DataFrame({"sg": ["g1"], "sn": ["n1"], "sv": ["v1"]}),
            foreign_keys=self._SCENARIO_FK,
        )
        dim = _res(
            "dim_scenario",
            pd.DataFrame(
                {
                    "scenario_group": ["g1", "g2"],
                    "scenario_name": ["n1", "n2"],
                    "scenario_variant": ["v1", "v2"],
                }
            ),
        )
        resources = {"fact": fact, "dim_scenario": dim}

        _filter_pruned_dimensions(resources)

        out = resources["dim_scenario"]["data"]
        assert len(out) == 1
        assert out.iloc[0]["scenario_name"] == "n1"

    def test_union_across_multiple_facts(self):
        f1 = _res("f1", pd.DataFrame({"model": ["a"]}), foreign_keys=self._MODEL_FK)
        f2 = _res("f2", pd.DataFrame({"model": ["b"]}), foreign_keys=self._MODEL_FK)
        dim = _res("dim_model", pd.DataFrame({"id": ["a", "b", "c"]}))
        resources = {"f1": f1, "f2": f2, "dim_model": dim}

        _filter_pruned_dimensions(resources)

        assert sorted(resources["dim_model"]["data"]["id"]) == ["a", "b"]

    def test_unreferenced_pruned_dimension_dropped(self):
        resources = {"dim_model": _res("dim_model", pd.DataFrame({"id": ["a", "b"]}))}

        with pytest.warns(UserWarning, match="no referenced rows"):
            _filter_pruned_dimensions(resources)

        assert "dim_model" not in resources

    def test_non_pruned_dimension_untouched(self):
        fact = _res(
            "fact",
            pd.DataFrame({"region": ["a"]}),
            foreign_keys=[
                {
                    "fields": ["region"],
                    "reference": {"resource": "dim_region", "fields": ["id"]},
                }
            ],
        )
        dim = _res("dim_region", pd.DataFrame({"id": ["a", "b", "c"]}))
        resources = {"fact": fact, "dim_region": dim}

        _filter_pruned_dimensions(resources)

        assert len(resources["dim_region"]["data"]) == 3


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

    def test_empty_resource_is_warned_and_skipped(
        self, make_package_spec, make_data_variable
    ):
        spec = make_package_spec(("res_empty", "res_ok"))
        registry = FakeRegistry(
            {
                "res_empty": make_data_variable(pd.DataFrame()),
                "res_ok": make_data_variable(pd.DataFrame({"id": ["a"]})),
            }
        )

        with pytest.warns(UserWarning, match="is empty"):
            result = resolve_resources(registry, spec)

        assert set(result) == {"res_ok"}

    def test_all_empty_raises(self, make_package_spec, make_data_variable):
        spec = make_package_spec(("res_a",))
        registry = FakeRegistry({"res_a": make_data_variable(pd.DataFrame())})

        # the empty-skip warning is asserted in the test above; silence it here
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with pytest.raises(ValueError, match="No resources to release"):
                resolve_resources(registry, spec)

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

    def test_referenced_dimension_added_as_resource(
        self, make_package_spec, make_data_variable, make_dimension
    ):
        dim_df = pd.DataFrame({"id": ["a", "b"], "label": ["A", "B"]})
        fact = make_data_variable(pd.DataFrame({"region": ["a", "b"]}))
        fact.foreign_keys = [_fk("dim_region")]
        dim = make_dimension(dim_df)
        spec = make_package_spec(("res_a",))
        registry = FakeRegistry({"res_a": fact, "dim_region": dim})

        result = resolve_resources(registry, spec)

        assert set(result) == {"res_a", "dim_region"}
        dim_resource = result["dim_region"]["data_resource"]
        assert isinstance(dim_resource, DataResource)
        assert dim_resource.name == "dim_region"
        pd.testing.assert_frame_equal(result["dim_region"]["data"], dim_df)

    def test_dimension_deduplicated_across_resources(
        self, make_package_spec, make_data_variable, make_dimension
    ):
        dim = make_dimension(pd.DataFrame({"id": ["a"], "label": ["A"]}))
        fact_a = make_data_variable(pd.DataFrame({"region": ["a"]}))
        fact_a.foreign_keys = [_fk("dim_region")]
        fact_b = make_data_variable(pd.DataFrame({"region": ["a"]}))
        fact_b.foreign_keys = [_fk("dim_region")]
        spec = make_package_spec(("res_a", "res_b"))
        registry = FakeRegistry({"res_a": fact_a, "res_b": fact_b, "dim_region": dim})

        result = resolve_resources(registry, spec)

        assert set(result) == {"res_a", "res_b", "dim_region"}

    def test_explicit_dimension_resource_not_duplicated(
        self, make_package_spec, make_data_variable, make_dimension
    ):
        # The dimension is both listed explicitly as a resource and referenced by
        # a fact: it must appear once (resolved in the first pass), not raise.
        dim_df = pd.DataFrame({"id": ["a", "b"], "label": ["A", "B"]})
        dim = make_dimension(dim_df)
        fact = make_data_variable(pd.DataFrame({"region": ["a"]}))
        fact.foreign_keys = [_fk("dim_region")]
        spec = make_package_spec(("res_a", "dim_region"))
        registry = FakeRegistry({"res_a": fact, "dim_region": dim})

        result = resolve_resources(registry, spec)

        assert set(result) == {"res_a", "dim_region"}
        pd.testing.assert_frame_equal(result["dim_region"]["data"], dim_df)

    def test_empty_dimension_warned_and_skipped(
        self, make_package_spec, make_data_variable, make_dimension
    ):
        fact = make_data_variable(pd.DataFrame({"region": ["a"]}))
        fact.foreign_keys = [_fk("dim_region")]
        dim = make_dimension(pd.DataFrame())
        spec = make_package_spec(("res_a",))
        registry = FakeRegistry({"res_a": fact, "dim_region": dim})

        with pytest.warns(UserWarning, match="has no data"):
            result = resolve_resources(registry, spec)

        assert set(result) == {"res_a"}

    def test_resolve_references_false_excludes_referenced(
        self, make_package_spec, make_data_variable, make_dimension
    ):
        fact = make_data_variable(pd.DataFrame({"region": ["a"]}))
        fact.foreign_keys = [_fk("dim_region")]
        dim = make_dimension(pd.DataFrame({"id": ["a"], "label": ["A"]}))
        spec = make_package_spec(("res_a",))
        registry = FakeRegistry({"res_a": fact, "dim_region": dim})

        result = resolve_resources(registry, spec, resolve_references=False)

        assert set(result) == {"res_a"}

    def test_resolve_references_false_drops_embedded_foreign_keys(
        self, make_package_spec, make_data_variable, contract_factory
    ):
        contract = _fact_contract_with_fk(contract_factory)
        fact = make_data_variable(pd.DataFrame({"region": ["a"]}), contract=contract)
        spec = make_package_spec(("res_a",))
        registry = FakeRegistry({"res_a": fact})

        with warnings.catch_warnings():
            warnings.simplefilter("error")  # dropping by design must not warn
            result = resolve_resources(registry, spec, resolve_references=False)

        assert set(result) == {"res_a"}
        assert result["res_a"]["data_resource"].table_schema.foreignKeys == []

    def test_resolve_references_true_keeps_present_foreign_keys(
        self, make_package_spec, make_data_variable, make_dimension, contract_factory
    ):
        contract = _fact_contract_with_fk(contract_factory)
        fact = make_data_variable(pd.DataFrame({"region": ["a"]}), contract=contract)
        fact.foreign_keys = [_fk("dim_region", fields=("region",), ref_fields=("id",))]
        dim = make_dimension(pd.DataFrame({"id": ["a"], "label": ["A"]}))
        spec = make_package_spec(("res_a",))
        registry = FakeRegistry({"res_a": fact, "dim_region": dim})

        result = resolve_resources(registry, spec, resolve_references=True)

        assert set(result) == {"res_a", "dim_region"}
        assert len(result["res_a"]["data_resource"].table_schema.foreignKeys) == 1

    def test_skipped_empty_reference_drops_foreign_keys_and_warns(
        self, make_package_spec, make_data_variable, make_dimension, contract_factory
    ):
        # Even in the default (include) path, a reference skipped as empty would
        # leave a dangling foreign key: it must be dropped, and that is surprising
        # enough to warn about.
        contract = _fact_contract_with_fk(contract_factory)
        fact = make_data_variable(pd.DataFrame({"region": ["a"]}), contract=contract)
        fact.foreign_keys = [_fk("dim_region", fields=("region",), ref_fields=("id",))]
        dim = make_dimension(pd.DataFrame())  # empty -> skipped
        spec = make_package_spec(("res_a",))
        registry = FakeRegistry({"res_a": fact, "dim_region": dim})

        # Capture (and thus consume) all warnings to keep the empty-skip notice
        # from leaking into the test output, then assert on the drop warning.
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = resolve_resources(registry, spec, resolve_references=True)

        assert any("Dropping foreign keys" in str(w.message) for w in caught)
        assert set(result) == {"res_a"}
        assert result["res_a"]["data_resource"].table_schema.foreignKeys == []

    def test_pruned_dimension_filtered_end_to_end(
        self, make_package_spec, make_data_variable, make_dimension, contract_factory
    ):
        # Wiring check: resolve_resources applies _filter_pruned_dimensions, so the
        # collected dim_model is reduced to the ids referenced by the fact.
        contract = _fact_contract_with_fk(contract_factory, target="dim_model")
        fact = make_data_variable(
            pd.DataFrame({"region": ["a", "b"]}), contract=contract
        )
        fact.foreign_keys = [_fk("dim_model", fields=("region",), ref_fields=("id",))]
        dim = make_dimension(
            pd.DataFrame({"id": ["a", "b", "c"], "label": list("ABC")})
        )
        spec = make_package_spec(("res_a",))
        registry = FakeRegistry({"res_a": fact, "dim_model": dim})

        result = resolve_resources(registry, spec)

        assert set(result) == {"res_a", "dim_model"}
        assert sorted(result["dim_model"]["data"]["id"]) == ["a", "b"]

    def test_referenced_fetch_error_wrapped_as_runtimeerror(
        self, make_package_spec, make_data_variable
    ):
        class _BadVar:
            @property
            def data(self):
                raise KeyError("boom")

        fact = make_data_variable(pd.DataFrame({"region": ["a"]}))
        fact.foreign_keys = [_fk("dim_region")]
        spec = make_package_spec(("res_a",))
        registry = FakeRegistry({"res_a": fact, "dim_region": _BadVar()})

        with pytest.raises(RuntimeError, match="Error fetching data for referenced"):
            resolve_resources(registry, spec, resolve_references=True)
