import pytest

from crosscontract.contracts.contracts.metadata_models import (
    Contributor,
    License,
    Source,
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
            match="Value error, A license must define at least one of `name` or",
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


class TestSource:
    def test_source_creation_valid(self):
        source = Source(
            title="Example Data Source",
            path="https://example.com/data.csv",
        )
        assert source.title == "Example Data Source"

    def test_source_creation_no_extra(self):
        with pytest.raises(
            ValueError,
            match="extra",
        ):
            Source(
                title="Example Data Source",
                path="https://example.com/data.csv",
                extra="This should not be allowed",
            )
