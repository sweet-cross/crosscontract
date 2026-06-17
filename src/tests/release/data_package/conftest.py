from unittest.mock import MagicMock

import pytest

from crosscontract.registry.variables import CrossBaseDimension
from crosscontract.registry.variables.data_variable import CrossDataVariable
from crosscontract.release.data_package.release_specification import (
    CrossDataPackageReleaseSpec,
    CrossDataResourceReleaseSpec,
)


@pytest.fixture
def make_resource_spec():
    """Factory for a resource spec; its name defaults to the fetch contract."""

    def _make(
        contract: str = "my_resource", fmt: str = "csv", **overrides
    ) -> CrossDataResourceReleaseSpec:
        data = {
            "data_instructions": {"fetch": {"contract": contract, "format": fmt}},
            **overrides,
        }
        return CrossDataResourceReleaseSpec.model_validate(data)

    return _make


@pytest.fixture
def make_package_spec():
    """Factory for a package spec with one resource per contract name."""

    def _make(
        contracts: tuple[str, ...] = ("my_resource",), **overrides
    ) -> CrossDataPackageReleaseSpec:
        data = {
            "name": "test-package",
            "title": "Test Package",
            "description": "A package for testing.",
            "resources": [
                {"data_instructions": {"fetch": {"contract": c}}} for c in contracts
            ],
            **overrides,
        }
        return CrossDataPackageReleaseSpec.model_validate(data)

    return _make


@pytest.fixture
def make_var_for_contract():
    """Factory for a variable mock exposing `contract_resource.contract`."""

    def _make(contract) -> MagicMock:
        var = MagicMock()
        var.contract_resource.contract = contract
        return var

    return _make


@pytest.fixture
def make_data_variable(contract_factory):
    """Factory for a `CrossDataVariable` mock that returns `df` from `get_data`
    and exposes a real contract via `contract_resource.contract`.
    """

    def _make(df, contract=None) -> MagicMock:
        var = MagicMock(spec=CrossDataVariable)
        var.get_data.return_value = df
        var.contract_resource.contract = contract or contract_factory.build()
        return var

    return _make


@pytest.fixture
def make_dimension(contract_factory):
    """Factory for a `CrossBaseDimension` mock exposing `data` and a real contract
    via `contract_resource.contract`.
    """

    def _make(df, contract=None) -> MagicMock:
        dim = MagicMock(spec=CrossBaseDimension)
        dim.data = df
        dim.contract_resource.contract = contract or contract_factory.build()
        return dim

    return _make
