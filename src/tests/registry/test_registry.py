# test_registry.py
import warnings
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from crosscontract.contracts import CrossContract
from crosscontract.registry import CrossDataVariable, CrossDimension, CrossRegistry

# ---------------------------------------------------------------------------
# Contracts & data
# ---------------------------------------------------------------------------
dim_contract_dict = {
    "name": "dim_region",
    "description": "A hierarchical dimension",
    "title": "Region",
    "tableschema": {
        "fields": [
            {"name": "id", "type": "string"},
            {"name": "label", "type": "string"},
            {"name": "level", "type": "integer"},
            {"name": "id_parent", "type": "string"},
        ],
    },
}

dim_data = pd.DataFrame(
    {
        "id": ["total", "cat_a", "cat_b"],
        "label": ["Total", "Category A", "Category B"],
        "level": [0, 1, 1],
        "id_parent": [None, "total", "total"],
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
    "my_data": (data_contract_dict, data_df),
    "simple_data": (simple_contract_dict, simple_data),
}


def _make_mock_contract_resource(name: str) -> MagicMock:
    """Build a mock ContractResource with a real contract for a given name."""
    contract_dict, df = _contract_catalog[name]
    contract = CrossContract.model_validate(contract_dict)
    cr = MagicMock()
    cr.contract = contract
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

    def test_contract_overview_filters_and_returns_expected_columns(self):
        # Arrange
        mock_client = MagicMock()
        mock_client.contracts.overview.return_value = pd.DataFrame(
            {
                "name": ["price", "dim_region", "volume"],
                "title": ["Price", "Region Dimension", "Volume"],
                "description": ["Price desc", "Region desc", "Volume desc"],
                "extra_col": ["x", "y", "z"],
            }
        )

        registry = CrossRegistry(client=mock_client)

        # Act
        result = registry.contract_overview

        # Assert
        assert list(result.columns) == ["name", "title", "description"]
        assert "dim_region" not in result["name"].values
        assert set(result["name"].values) == {"price", "volume"}


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
        assert "dim_region" in var.dimensions

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

    def test_fk_dimension_not_fetched_twice(self, registry: CrossRegistry, mock_client):
        """If the dimension is already loaded, add_variable should reuse it."""
        registry.add_variable("dim_region")
        mock_client.contracts.get.reset_mock()
        registry.add_variable("my_data")
        # dim_region should NOT be fetched again
        calls = [c.args[0] for c in mock_client.contracts.get.call_args_list]
        assert "dim_region" not in calls

    def test_circular_foreign_key_skipped(self, make_contract_resource):
        """Circular FK references are silently skipped by the loading guard."""
        from unittest.mock import MagicMock

        contract_a = {
            "name": "var_a",
            "description": "Variable A",
            "title": "A",
            "tableschema": {
                "fields": [
                    {"name": "region", "type": "string"},
                    {"name": "value", "type": "number"},
                ],
                "foreignKeys": [
                    {
                        "fields": ["region"],
                        "reference": {"resource": "var_b", "fields": ["region"]},
                    }
                ],
            },
        }

        contract_b = {
            "name": "var_b",
            "description": "Variable B",
            "title": "B",
            "tableschema": {
                "fields": [
                    {"name": "region", "type": "string"},
                    {"name": "value", "type": "number"},
                ],
                "foreignKeys": [
                    {
                        "fields": ["region"],
                        "reference": {"resource": "var_a", "fields": ["region"]},
                    }
                ],
            },
        }

        df = pd.DataFrame({"region": ["r1"], "value": [1]})
        cr_a = make_contract_resource(data=df, contract_dict=contract_a)
        cr_b = make_contract_resource(data=df, contract_dict=contract_b)

        client = MagicMock()
        client.contracts.get.side_effect = lambda name: (
            cr_a if name == "var_a" else cr_b
        )

        reg = CrossRegistry(client=client)

        # Should not raise RecursionError
        reg.add_variable("var_a")

        # Both variables loaded
        assert "var_a" in reg._variables
        assert "var_b" in reg._variables

        # Loading sentinel is clean after completion
        assert reg._loading == set()

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
            cr.get_data.return_value = df.copy()
            return cr

        mock_client.contracts.get.side_effect = _lookup

        registry.add_variable("hierarchical")
        var = registry._variables["hierarchical"]
        assert var.dimensions == {}

    def test_circular_fk_warns(self, make_contract_resource):
        """Circular FK emits a warning when the loading guard triggers."""

        client = MagicMock()
        reg = CrossRegistry(client=client)

        # Simulate the condition: ref_name is in _loading but not in _variables
        reg._loading.add("var_b")

        contract_a = {
            "name": "var_a",
            "description": "A",
            "title": "A",
            "tableschema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "value", "type": "number"},
                ],
                "foreignKeys": [
                    {
                        "fields": ["id"],
                        "reference": {"resource": "var_b", "fields": ["id"]},
                    }
                ],
            },
        }

        df = pd.DataFrame({"id": ["x"], "value": [1]})
        cr_a = make_contract_resource(data=df, contract_dict=contract_a)
        client.contracts.get.return_value = cr_a

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            reg.add_variable("var_a")

        assert len(w) == 1
        assert "Circular foreign key reference" in str(w[0].message)
        assert "var_b" in str(w[0].message)

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
