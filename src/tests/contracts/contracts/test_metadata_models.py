import pytest

from crosscontract.contracts.contracts.metadata_models import License


class TestLicense:
    def test_license_creation_valid(self):
        license = License(
            title="Creative Commons Attribution 4.0",
            path="https://creativecommons.org/licenses/by/4.0/",
        )
        assert license.title == "Creative Commons Attribution 4.0"

    def test_license_creation_invalid(self):
        with pytest.raises(
            ValueError,
            match="A License object must contain at least a",
        ):
            License()
