import pytest
from pydantic import ValidationError

from crosscontract.release.data_package.release_specification import (
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
