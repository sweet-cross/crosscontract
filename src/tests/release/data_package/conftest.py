from unittest.mock import MagicMock

import pytest

from crosscontract.release.data_package.release_specification import (
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
def make_var_for_contract():
    """Factory for a variable mock exposing `contract_resource.contract`."""

    def _make(contract) -> MagicMock:
        var = MagicMock()
        var.contract_resource.contract = contract
        return var

    return _make
