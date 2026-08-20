# test_registry.py
import warnings
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from crosscontract.contracts import CrossContract
from crosscontract.contracts.schema.subschemas import BaseDimensionSchema
from crosscontract.registry import (
    CrossDataVariable,
    CrossDimension,
    CrossFlexibleDimension,
    CrossRegistry,
)

# ---------------------------------------------------------------------------
# Contracts & data
# ---------------------------------------------------------------------------
# Rigid Dimension: tableschema is auto-injected from the DimensionSchema
# template (id, level, parent_id, label, description). The data DataFrame
# below mirrors what `cr.get_data()` returns to the registry-side wrapper.
dim_contract_dict = {
    "name": "dim_region",
    "description": "A hierarchical dimension",
    "title": "Region",
    "contract_type": "Dimension",
    "tableschema": {},
}

dim_data = pd.DataFrame(
    {
        "id": ["total", "cat_a", "cat_b"],
        "label": ["Total", "Category A", "Category B"],
        "level": [0, 1, 1],
        "parent_id": [None, "total", "total"],
    }
)

flex_dim_contract_dict = {
    "name": "dim_currency",
    "description": "A flexible (non-hierarchical) dimension",
    "title": "Currency",
    "contract_type": "FlexibleDimension",
    "tableschema": {
        "primaryKey": ["code"],
        "fields": [
            {"name": "code", "type": "string"},
            {"name": "label", "type": "string"},
            {"name": "description", "type": "string"},
        ],
    },
}

flex_dim_data = pd.DataFrame(
    {
        "code": ["EUR", "USD"],
        "label": ["Euro", "US Dollar"],
        "description": ["European currency", "American currency"],
    }
)

data_contract_dict = {
    "name": "my_data",
    "description": "Test data variable",
    "title": "My Data",
    "tableschema": {
        "fields": [
            {"name": "region", "type": "string"},
            {"name": "value", "type": "number"},
        ],
        "foreignKeys": [
            {
                "fields": ["region"],
                "reference": {"resource": "dim_region", "fields": ["id"]},
            }
        ],
    },
}

data_df = pd.DataFrame(
    {
        "region": ["cat_a", "cat_b"],
        "value": [10.0, 20.0],
    }
)

flex_fk_contract_dict = {
    "name": "prices",
    "description": "Data variable with FK to a flexible dimension",
    "title": "Prices",
    "tableschema": {
        "fields": [
            {"name": "currency", "type": "string"},
            {"name": "value", "type": "number"},
        ],
        "foreignKeys": [
            {
                "fields": ["currency"],
                "reference": {"resource": "dim_currency", "fields": ["code"]},
            }
        ],
    },
}

flex_fk_df = pd.DataFrame(
    {
        "currency": ["EUR", "USD"],
        "value": [1.0, 1.1],
    }
)

simple_contract_dict = {
    "name": "simple_data",
    "description": "No foreign keys",
    "title": "Simple",
    "tableschema": {
        "fields": [
            {"name": "category", "type": "string"},
            {"name": "value", "type": "number"},
        ],
    },
}

simple_data = pd.DataFrame(
    {
        "category": ["a", "b"],
        "value": [1.0, 2.0],
    }
)

# ---------------------------------------------------------------------------
# Map of contract name -> (contract_dict, dataframe)
# Used by the mock client to return the correct resource for each name
# ---------------------------------------------------------------------------
_contract_catalog = {
    "dim_region": (dim_contract_dict, dim_data),
    "dim_currency": (flex_dim_contract_dict, flex_dim_data),
    "my_data": (data_contract_dict, data_df),
    "prices": (flex_fk_contract_dict, flex_fk_df),
    "simple_data": (simple_contract_dict, simple_data),
}


def _make_mock_contract_resource(name: str) -> MagicMock:
    """Build a mock ContractResource with a real contract for a given name."""
    contract_dict, df = _contract_catalog[name]
    contract = CrossContract.model_validate(contract_dict)
    cr = MagicMock()
    cr.contract = contract
    cr.is_dimension = isinstance(contract.tableschema, BaseDimensionSchema)
    cr.get_data.return_value = df.copy()
    return cr


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_client() -> MagicMock:
    """A mock CrossClient whose contracts.get() returns the right resource."""
    client = MagicMock()
    client.contracts.get.side_effect = _make_mock_contract_resource
    return client


@pytest.fixture
def registry(mock_client) -> CrossRegistry:
    return CrossRegistry(client=mock_client)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestInit:
    def test_with_client(self, mock_client):
        reg = CrossRegistry(client=mock_client)
        assert reg._client is mock_client

    def test_missing_credentials_raises(self):
        with pytest.raises(ValueError, match="username and password"):
            CrossRegistry()

    def test_missing_password_raises(self):
        with pytest.raises(ValueError, match="username and password"):
            CrossRegistry(username="user")

    def test_with_username_password(self):
        with patch("crosscontract.registry.registry.CrossClient") as mock_cls:
            reg = CrossRegistry(username="user", password="pass")
            mock_cls.assert_called_once_with(username="user", password="pass")
            assert reg._client is mock_cls.return_value

    def _overview_payload(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "name": ["price", "dim_region", "dim_currency", "volume"],
                "title": ["Price", "Region", "Currency", "Volume"],
                "description": ["P", "R", "C", "V"],
                "contract_type": [
                    "ValueVariable",
                    "Dimension",
                    "FlexibleDimension",
                    "ValueVariable",
                ],
                "extra_col": ["x", "y", "z", "w"],
            }
        )

    def test_contract_overview_returns_all_contracts(self):
        mock_client = MagicMock()
        mock_client.contracts.overview.return_value = self._overview_payload()
        registry = CrossRegistry(client=mock_client)

        result = registry.contract_overview

        assert list(result.columns) == [
            "name",
            "title",
            "description",
            "contract_type",
        ]
        assert set(result["name"].values) == {
            "price",
            "dim_region",
            "dim_currency",
            "volume",
        }

    def test_get_contract_overview_no_filter_matches_property(self):
        mock_client = MagicMock()
        mock_client.contracts.overview.return_value = self._overview_payload()
        registry = CrossRegistry(client=mock_client)

        assert registry.get_contract_overview().equals(registry.contract_overview)

    def test_get_contract_overview_filters_by_single_type(self):
        mock_client = MagicMock()
        mock_client.contracts.overview.return_value = self._overview_payload()
        registry = CrossRegistry(client=mock_client)

        result = registry.get_contract_overview(contract_type="Dimension")

        assert list(result.columns) == [
            "name",
            "title",
            "description",
            "contract_type",
        ]
        assert set(result["name"].values) == {"dim_region"}

    def test_get_contract_overview_filters_by_multiple_types(self):
        mock_client = MagicMock()
        mock_client.contracts.overview.return_value = self._overview_payload()
        registry = CrossRegistry(client=mock_client)

        result = registry.get_contract_overview(
            contract_type=["Dimension", "FlexibleDimension"]
        )

        assert set(result["name"].values) == {"dim_region", "dim_currency"}


class TestAddVariable:
    def test_add_data_variable(self, registry: CrossRegistry, mock_client):
        registry.add_variable("simple_data")
        assert "simple_data" in registry._variables
        assert isinstance(registry._variables["simple_data"], CrossDataVariable)
        mock_client.contracts.get.assert_called_with("simple_data")

    def test_add_dimension(self, registry: CrossRegistry):
        registry.add_variable("dim_region")
        assert "dim_region" in registry._variables
        assert isinstance(registry._variables["dim_region"], CrossDimension)

    def test_add_data_variable_resolves_fk_dimensions(
        self, registry: CrossRegistry, mock_client
    ):
        registry.add_variable("my_data")
        # dim_region should have been auto-loaded
        assert "dim_region" in registry._variables
        assert isinstance(registry._variables["dim_region"], CrossDimension)
        # and hydrated into the data variable
        var = registry._variables["my_data"]
        assert "region" in var.dimensions

    def test_duplicate_raises(self, registry: CrossRegistry):
        registry.add_variable("simple_data")
        with pytest.raises(ValueError, match="already exists"):
            registry.add_variable("simple_data")

    def test_overwrite_data_variable(self, registry: CrossRegistry):
        registry.add_variable("simple_data")
        registry.add_variable("simple_data", overwrite=True)
        assert isinstance(registry._variables["simple_data"], CrossDataVariable)

    def test_overwrite_dimension_rejected(self, registry: CrossRegistry):
        registry.add_variable("dim_region")
        with pytest.raises(ValueError, match="Dimension.*cannot be overwritten"):
            registry.add_variable("dim_region", overwrite=True)

    def test_filters_on_value_variable_emits_deprecation_warning(
        self, registry: CrossRegistry
    ):
        with pytest.warns(FutureWarning, match="deprecated"):
            var = registry.add_variable("simple_data", filters={"category": "a"})
        assert var._filters == {"category": "a"}

    def test_filters_on_dimension_emits_deprecation_warning_and_is_ignored(
        self, registry: CrossRegistry
    ):
        with pytest.warns(FutureWarning, match="deprecated"):
            registry.add_variable("dim_region", filters={"id": "total"})
        assert isinstance(registry._variables["dim_region"], CrossDimension)

    def test_add_variable_without_filters_emits_no_warning(
        self, registry: CrossRegistry
    ):
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            registry.add_variable("simple_data")

    def test_fk_dimension_not_fetched_twice(self, registry: CrossRegistry, mock_client):
        """If the dimension is already loaded, add_variable should reuse it."""
        registry.add_variable("dim_region")
        mock_client.contracts.get.reset_mock()
        registry.add_variable("my_data")
        # dim_region should NOT be fetched again
        calls = [c.args[0] for c in mock_client.contracts.get.call_args_list]
        assert "dim_region" not in calls

    def test_add_flexible_dimension(self, registry: CrossRegistry):
        registry.add_variable("dim_currency")
        assert isinstance(registry._variables["dim_currency"], CrossFlexibleDimension)

    def test_flexible_dimension_fk_resolved(self, registry: CrossRegistry):
        registry.add_variable("prices")
        assert isinstance(registry._variables["dim_currency"], CrossFlexibleDimension)
        var = registry._variables["prices"]
        assert "currency" in var.dimensions
        assert isinstance(var.dimensions["currency"], CrossFlexibleDimension)

    def test_composite_fk_dimension_loaded_but_not_attached(
        self, registry: CrossRegistry, mock_client
    ):
        """Composite-FK dimension targets are still loaded into the registry
        so users can access them directly, but they're not auto-attached to
        the data variable's `.dimensions` dict."""
        from copy import deepcopy

        catalog = deepcopy(_contract_catalog)
        catalog["dim_scenario"] = (
            {
                "name": "dim_scenario",
                "description": "Composite-key scenario dimension",
                "title": "Scenario",
                "contract_type": "FlexibleDimension",
                "tableschema": {
                    "primaryKey": ["model", "scenario_name"],
                    "fields": [
                        {"name": "model", "type": "string"},
                        {"name": "scenario_name", "type": "string"},
                        {"name": "label", "type": "string"},
                        {"name": "description", "type": "string"},
                    ],
                },
            },
            pd.DataFrame(
                {
                    "model": ["m1", "m2"],
                    "scenario_name": ["s1", "s2"],
                    "label": ["M1/S1", "M2/S2"],
                    "description": ["", ""],
                }
            ),
        )
        catalog["uses_scenario"] = (
            {
                "name": "uses_scenario",
                "description": "References dim_scenario via composite FK",
                "title": "Uses scenario",
                "tableschema": {
                    "fields": [
                        {"name": "model", "type": "string"},
                        {"name": "scenario_name", "type": "string"},
                        {"name": "value", "type": "number"},
                    ],
                    "foreignKeys": [
                        {
                            "fields": ["model", "scenario_name"],
                            "reference": {
                                "resource": "dim_scenario",
                                "fields": ["model", "scenario_name"],
                            },
                        }
                    ],
                },
            },
            pd.DataFrame(
                {
                    "model": ["m1", "m2"],
                    "scenario_name": ["s1", "s2"],
                    "value": [1.0, 2.0],
                }
            ),
        )

        def _lookup(name):
            contract_dict, df = catalog[name]
            contract = CrossContract.model_validate(contract_dict)
            cr = MagicMock()
            cr.contract = contract
            cr.is_dimension = isinstance(contract.tableschema, BaseDimensionSchema)
            cr.get_data.return_value = df.copy()
            return cr

        mock_client.contracts.get.side_effect = _lookup

        registry.add_variable("uses_scenario")

        # dimension was loaded into the registry and is reachable directly
        assert "dim_scenario" in registry._variables
        assert isinstance(registry._variables["dim_scenario"], CrossFlexibleDimension)
        # ...but not auto-attached to the data variable
        assert registry._variables["uses_scenario"].dimensions == {}

    def test_self_referencing_fk_skipped(self, registry: CrossRegistry, mock_client):
        """A contract with a self-referencing FK (resource=None) should not
        trigger recursive loading."""
        from copy import deepcopy

        catalog = deepcopy(_contract_catalog)
        catalog["hierarchical"] = (
            {
                "name": "hierarchical",
                "description": "Self-referencing",
                "title": "Hierarchical",
                "tableschema": {
                    "fields": [
                        {"name": "id", "type": "string"},
                        {"name": "parent_id", "type": "string"},
                        {"name": "value", "type": "number"},
                    ],
                    "foreignKeys": [
                        {
                            "fields": ["parent_id"],
                            "reference": {"resource": None, "fields": ["id"]},
                        }
                    ],
                },
            },
            pd.DataFrame(
                {"id": ["a", "b"], "parent_id": [None, "a"], "value": [1.0, 2.0]}
            ),
        )

        def _lookup(name):
            contract_dict, df = catalog[name]
            contract = CrossContract.model_validate(contract_dict)
            cr = MagicMock()
            cr.contract = contract
            cr.is_dimension = isinstance(contract.tableschema, BaseDimensionSchema)
            cr.get_data.return_value = df.copy()
            return cr

        mock_client.contracts.get.side_effect = _lookup

        registry.add_variable("hierarchical")
        var = registry._variables["hierarchical"]
        assert var.dimensions == {}

    def test_non_dimension_fk_target_not_added_as_dimension(
        self, make_contract_resource
    ):
        """FK targets that are not CrossDimension instances are loaded but not
        added as dimensions on the referencing variable."""
        contract_a = {
            "name": "var_a",
            "description": "References a non-dimension",
            "title": "A",
            "tableschema": {
                "fields": [
                    {"name": "ref_id", "type": "string"},
                    {"name": "value", "type": "number"},
                ],
                "foreignKeys": [
                    {
                        "fields": ["ref_id"],
                        "reference": {"resource": "var_b", "fields": ["ref_id"]},
                    }
                ],
            },
        }
        contract_b = {
            "name": "var_b",
            "description": "A plain data variable, not a dimension",
            "title": "B",
            "tableschema": {
                "fields": [
                    {"name": "ref_id", "type": "string"},
                    {"name": "score", "type": "number"},
                ],
            },
        }

        df_a = pd.DataFrame({"ref_id": ["x"], "value": [1]})
        df_b = pd.DataFrame({"ref_id": ["x"], "score": [99]})
        cr_a = make_contract_resource(data=df_a, contract_dict=contract_a)
        cr_b = make_contract_resource(data=df_b, contract_dict=contract_b)

        client = MagicMock()
        client.contracts.get.side_effect = lambda name: (
            cr_a if name == "var_a" else cr_b
        )

        reg = CrossRegistry(client=client)
        reg.add_variable("var_a")

        # var_b was loaded into the registry
        assert "var_b" in reg._variables
        assert isinstance(reg._variables["var_b"], CrossDataVariable)
        # but NOT added as a dimension on var_a
        assert reg._variables["var_a"].dimensions == {}


class TestGetVariable:
    def test_explicit_get(self, registry: CrossRegistry):
        registry.add_variable("simple_data")
        var = registry.get_variable("simple_data")
        assert isinstance(var, CrossDataVariable)

    def test_lazy_load(self, registry: CrossRegistry):
        var = registry.get_variable("simple_data")
        assert isinstance(var, CrossDataVariable)

    def test_not_found_raises_key_error(self, registry: CrossRegistry, mock_client):
        mock_client.contracts.get.side_effect = Exception("Not found")
        with pytest.raises(KeyError, match="Could not load variable"):
            registry.get_variable("nonexistent")


class TestDunderMethods:
    def test_getattr_dot_access(self, registry: CrossRegistry):
        registry.add_variable("simple_data")
        var = registry.simple_data
        assert isinstance(var, CrossDataVariable)

    def test_getattr_lazy_load(self, registry: CrossRegistry):
        var = registry.simple_data
        assert isinstance(var, CrossDataVariable)

    def test_getattr_underscore_raises(self, registry: CrossRegistry):
        with pytest.raises(AttributeError):
            _ = registry._nonexistent

    def test_getattr_not_found_raises_attribute_error(
        self, registry: CrossRegistry, mock_client
    ):
        mock_client.contracts.get.side_effect = Exception("Not found")
        with pytest.raises(AttributeError):
            _ = registry.nonexistent

    def test_hasattr_returns_false_for_missing(
        self, registry: CrossRegistry, mock_client
    ):
        mock_client.contracts.get.side_effect = Exception("Not found")
        assert not hasattr(registry, "nonexistent")

    def test_getitem_bracket_access(self, registry: CrossRegistry):
        registry.add_variable("simple_data")
        var = registry["simple_data"]
        assert isinstance(var, CrossDataVariable)

    def test_getitem_lazy_load(self, registry: CrossRegistry):
        var = registry["simple_data"]
        assert isinstance(var, CrossDataVariable)

    def test_dir_includes_variables(self, registry: CrossRegistry):
        registry.add_variable("simple_data")
        registry.add_variable("dim_region")
        entries = dir(registry)
        assert "simple_data" in entries
        assert "dim_region" in entries

    def test_dir_includes_standard_attributes(self, registry: CrossRegistry):
        entries = dir(registry)
        assert "add_variable" in entries
        assert "get_variable" in entries
