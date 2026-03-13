# test_registry.py

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

    def test_self_referencing_fk_skipped(self, registry: CrossRegistry, mock_client):
        """A contract with a self-referencing FK (resource=None) should not
        trigger recursive loading."""
        self_ref_contract = {
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
        }
        self_ref_data = pd.DataFrame(
            {"id": ["a", "b"], "parent_id": [None, "a"], "value": [1.0, 2.0]}
        )
        _contract_catalog["hierarchical"] = (self_ref_contract, self_ref_data)

        registry.add_variable("hierarchical")
        # should load without recursion error, and no dimensions added
        var = registry._variables["hierarchical"]
        assert var.dimensions == {}


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
