import pytest

from crosscontract.contracts.contracts.metadata_models import (
    Contributor,
    DataSource,
    License,
)


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

    def test_license_creation_no_extra(self):
        with pytest.raises(
            ValueError,
            match="extra",
        ):
            License(
                title="Creative Commons Attribution 4.0",
                path="https://creativecommons.org/licenses/by/4.0/",
                extra="This should not be allowed",
            )


class TestContributor:
    def test_contributor_creation_valid(self):
        contributor = Contributor(
            title="Jane Doe",
        )
        assert contributor.title == "Jane Doe"

    def test_contributor_creation_no_extra(self):
        with pytest.raises(
            ValueError,
            match="extra",
        ):
            Contributor(
                title="Jane Doe",
                extra="This should not be allowed",
            )


class TestDataSource:
    def test_datasource_creation_valid(self):
        datasource = DataSource(
            title="Example Data Source",
            path="https://example.com/data.csv",
        )
        assert datasource.title == "Example Data Source"

    def test_datasource_creation_no_extra(self):
        with pytest.raises(
            ValueError,
            match="extra",
        ):
            DataSource(
                title="Example Data Source",
                path="https://example.com/data.csv",
                extra="This should not be allowed",
            )
