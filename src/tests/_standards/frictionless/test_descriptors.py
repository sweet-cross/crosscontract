import pytest
from pydantic import ValidationError

from crosscontract._standards.frictionless import (
    Contributor,
    DataPackage,
    DataResource,
    License,
    Source,
    TableSchema,
)


class TestDataResourceComposition:
    """`DataResource` composes `ResourceMetaData` and `FileMetaData`.

    The per-mixin rules are exercised in `test_metadata.py`; here we check that
    the two combine into a single, coherent descriptor.
    """

    def test_path_only_resource_is_valid(self):
        resource = DataResource(name="my-data", path="file.csv")
        assert resource.path == ["file.csv"]
        assert resource.data is None
        assert resource.profile == "data-resource"
        assert resource.encoding == "utf-8"

    def test_data_only_resource_is_valid(self):
        resource = DataResource(name="my-data", data=[{"x": 1}])
        assert resource.path == []

    def test_name_required_from_resource_metadata(self):
        with pytest.raises(ValidationError):
            DataResource(path="file.csv")

    def test_data_or_path_required_from_file_metadata(self):
        with pytest.raises(ValidationError):
            DataResource(name="my-data")

    def test_schema_alias_round_trips(self):
        resource = DataResource(
            name="my-data", path="file.csv", schema={"fields": [{"name": "id"}]}
        )
        assert isinstance(resource.table_schema, TableSchema)
        dumped = resource.model_dump(exclude_none=True)
        assert "schema" in dumped
        assert "table_schema" not in dumped

    def test_extra_key_is_preserved(self):
        resource = DataResource(name="my-data", path="file.csv", custom="x")
        assert resource.model_dump()["custom"] == "x"


class TestDataPackage:
    """`resources` is the only field `DataPackage` adds (and requires)."""

    def test_minimal_package(self):
        package = DataPackage(resources=[{"name": "my-data", "path": "file.csv"}])
        assert len(package.resources) == 1
        assert isinstance(package.resources[0], DataResource)
        assert package.profile == "data-package"

    def test_empty_resources_is_rejected(self):
        with pytest.raises(ValidationError):
            DataPackage(resources=[])

    def test_resources_is_required(self):
        with pytest.raises(ValidationError):
            DataPackage()

    def test_nested_metadata_is_parsed(self):
        package = DataPackage(
            name="my-package",
            resources=[{"name": "my-data", "path": "file.csv"}],
            contributors=[{"title": "Joe Bloggs", "role": "author"}],
            licenses=[{"name": "CC-BY-4.0"}],
            sources=[{"title": "World Bank"}],
        )
        assert isinstance(package.contributors[0], Contributor)
        assert isinstance(package.licenses[0], License)
        assert isinstance(package.sources[0], Source)

    def test_extra_key_is_preserved(self):
        package = DataPackage(
            resources=[{"name": "my-data", "path": "file.csv"}], custom="y"
        )
        assert package.model_dump()["custom"] == "y"


class TestRoundTrip:
    """A descriptor survives a `model_dump` / `model_validate` round-trip."""

    def test_package_round_trip(self):
        package = DataPackage(
            name="my-package",
            resources=[
                {
                    "name": "my-data",
                    "path": "file.csv",
                    "schema": {"fields": [{"name": "id"}]},
                }
            ],
        )
        dumped = package.model_dump(mode="json", exclude_none=True)
        reloaded = DataPackage.model_validate(dumped)
        assert reloaded == package
