import pytest
from pydantic import ValidationError

from crosscontract.contracts.release import (
    CrossDataPackageReleaseSpec,
)


def _resource_dict(contract: str) -> dict:
    """A resource spec dict whose name defaults to its fetch contract."""
    return {"data_instructions": {"fetch": {"contract": contract}}}


class TestUniqueResourceNames:
    def test_duplicate_resource_names_rejected(self):
        # Two resources fetching the same contract resolve to the same name.
        with pytest.raises(ValidationError, match="must be unique"):
            CrossDataPackageReleaseSpec.model_validate(
                {
                    "name": "test-package",
                    "resources": [
                        _resource_dict("same_contract"),
                        _resource_dict("same_contract"),
                    ],
                }
            )

    def test_unique_resource_names_accepted(self):
        spec = CrossDataPackageReleaseSpec.model_validate(
            {
                "name": "test-package",
                "resources": [
                    _resource_dict("contract_a"),
                    _resource_dict("contract_b"),
                ],
            }
        )
        assert [r.name for r in spec.resources] == ["contract_a", "contract_b"]


class TestExports:
    def test_specs_reexported(self):
        import crosscontract.contracts as contracts
        import crosscontract.contracts.release as specs

        for name in ("CrossDataPackageReleaseSpec", "CrossDataResourceReleaseSpec"):
            assert getattr(contracts, name) is getattr(specs, name)
            assert name in contracts.__all__

    def test_data_instructions_exported_only_from_contracts_release(self):
        import crosscontract.contracts as contracts
        import crosscontract.contracts.release as specs

        assert "DataInstructions" in specs.__all__
        assert "DataInstructions" not in contracts.__all__
