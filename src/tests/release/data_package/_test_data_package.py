import json
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest
import yaml
from polyfactory.factories.pydantic_factory import ModelFactory
from pydantic import ValidationError

from crosscontract.release import CrossDataResource
from crosscontract.release.data_package.data_package import CrossDataPackage

_SCHEMA_PATH = Path(__file__).parent / "data-package.json"


def _make_package(contract_factory: type[ModelFactory], **kwargs) -> CrossDataPackage:
    resource = CrossDataResource.from_contract(
        contract_factory.build(), "data/file.csv"
    )
    return CrossDataPackage(
        name="test-package",
        title="Test Package",
        description="A package for testing.",
        resources=[resource],
        **kwargs,
    )


class TestToDescriptor:
    def test_profile_is_data_package(self, contract_factory: type[ModelFactory]):
        pkg = _make_package(contract_factory)
        descriptor = pkg.to_descriptor()
        assert descriptor["profile"] == "data-package"

    def test_resources_use_frictionless_schema_key(
        self, contract_factory: type[ModelFactory]
    ):
        pkg = _make_package(contract_factory)
        descriptor = pkg.to_descriptor()
        for resource in descriptor["resources"]:
            assert "schema" in resource
            assert "tableschema" not in resource

    def test_package_metadata_present(self, contract_factory: type[ModelFactory]):
        pkg = _make_package(contract_factory)
        descriptor = pkg.to_descriptor()
        assert descriptor["name"] == "test-package"
        assert descriptor["title"] == "Test Package"
        assert descriptor["description"] == "A package for testing."

    def test_none_fields_excluded(self, contract_factory: type[ModelFactory]):
        pkg = _make_package(contract_factory)
        assert pkg.contributors is None
        assert pkg.sources is None
        assert pkg.licenses is None
        descriptor = pkg.to_descriptor()
        assert "contributors" not in descriptor
        assert "sources" not in descriptor
        assert "licenses" not in descriptor

    def test_optional_fields_included_when_set(
        self, contract_factory: type[ModelFactory]
    ):
        from crosscontract.contracts.contracts.metadata_models import (
            Contributor,
            DataSource,
            License,
        )

        pkg = _make_package(
            contract_factory,
            licenses=[License(name="CC-BY-4.0")],
            contributors=[Contributor(title="Jane Doe")],
            sources=[DataSource(title="World Bank")],
        )
        descriptor = pkg.to_descriptor()
        assert "licenses" in descriptor
        assert descriptor["licenses"][0]["name"] == "CC-BY-4.0"
        assert "contributors" in descriptor
        assert descriptor["contributors"][0]["title"] == "Jane Doe"
        assert "sources" in descriptor
        assert descriptor["sources"][0]["title"] == "World Bank"

    def test_resource_count_matches(self, contract_factory: type[ModelFactory]):
        r1 = CrossDataResource.from_contract(
            contract_factory.build(name="first-contract"), "data/first.csv"
        )
        r2 = CrossDataResource.from_contract(
            contract_factory.build(name="second-contract"), "data/second.csv"
        )
        pkg = CrossDataPackage(
            name="multi-package",
            title="Multi",
            description="Two resources.",
            resources=[r1, r2],
        )
        descriptor = pkg.to_descriptor()
        assert len(descriptor["resources"]) == 2

    def test_descriptor_is_independent_of_model_dump(
        self, contract_factory: type[ModelFactory]
    ):
        # model_dump stays neutral: resources carry the internal `table_schema`
        # name, not the Frictionless `schema` wire-name.
        pkg = _make_package(contract_factory)
        raw = pkg.model_dump()
        for resource in raw["resources"]:
            assert "table_schema" in resource
            assert "schema" not in resource

    def test_frictionless_schema_compliance(self, contract_factory: type[ModelFactory]):
        frictionless_schema = json.loads(_SCHEMA_PATH.read_text())
        pkg = _make_package(contract_factory)
        descriptor = pkg.to_descriptor()
        jsonschema.validate(instance=descriptor, schema=frictionless_schema)

    def test_resource_schema_content_matches_contract(
        self, contract_factory: type[ModelFactory]
    ):
        contract = contract_factory.build()
        resource = CrossDataResource.from_contract(contract, "data/file.csv")
        pkg = CrossDataPackage(
            name="test-package",
            title="Test Package",
            description="A package for testing.",
            resources=[resource],
        )
        descriptor = pkg.to_descriptor()
        expected_schema = resource.model_dump(mode="json", exclude_none=True)[
            "table_schema"
        ]
        assert descriptor["resources"][0]["schema"] == expected_schema


class TestOptionalPackageFields:
    def test_id_included_when_set(self, contract_factory: type[ModelFactory]):
        pkg = _make_package(contract_factory, id="10.1234/example-doi")
        assert pkg.to_descriptor()["id"] == "10.1234/example-doi"

    def test_id_omitted_when_none(self, contract_factory: type[ModelFactory]):
        pkg = _make_package(contract_factory)
        assert "id" not in pkg.to_descriptor()

    def test_homepage_included_when_set(self, contract_factory: type[ModelFactory]):
        pkg = _make_package(contract_factory, homepage="https://example.com")
        descriptor = pkg.to_descriptor()
        assert "homepage" in descriptor
        assert "example.com" in descriptor["homepage"]

    def test_homepage_omitted_when_none(self, contract_factory: type[ModelFactory]):
        pkg = _make_package(contract_factory)
        assert "homepage" not in pkg.to_descriptor()

    def test_homepage_rejects_non_url(self, contract_factory: type[ModelFactory]):
        with pytest.raises(ValidationError):
            _make_package(contract_factory, homepage="not-a-url")

    def test_created_serializes_to_string(self, contract_factory: type[ModelFactory]):
        ts = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)
        pkg = _make_package(contract_factory, created=ts)
        descriptor = pkg.to_descriptor()
        assert "created" in descriptor
        assert isinstance(descriptor["created"], str)
        assert "2024-06-01" in descriptor["created"]

    def test_created_omitted_when_none(self, contract_factory: type[ModelFactory]):
        pkg = _make_package(contract_factory)
        assert "created" not in pkg.to_descriptor()

    def test_created_survives_to_file_json(
        self, contract_factory: type[ModelFactory], tmp_path
    ):
        ts = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)
        pkg = _make_package(contract_factory, created=ts)
        out = tmp_path / "package.json"
        pkg.to_file(out)
        content = json.loads(out.read_text())
        assert isinstance(content["created"], str)

    def test_created_survives_to_file_yaml(
        self, contract_factory: type[ModelFactory], tmp_path
    ):
        ts = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)
        pkg = _make_package(contract_factory, created=ts)
        out = tmp_path / "package.yaml"
        pkg.to_file(out)
        with out.open() as f:
            content = yaml.safe_load(f)
        assert "created" in content


class TestEmptyListToNone:
    def test_empty_contributors_collapses_to_none(
        self, contract_factory: type[ModelFactory]
    ):
        pkg = _make_package(contract_factory, contributors=[])
        assert pkg.contributors is None
        assert "contributors" not in pkg.to_descriptor()

    def test_empty_sources_collapses_to_none(
        self, contract_factory: type[ModelFactory]
    ):
        pkg = _make_package(contract_factory, sources=[])
        assert pkg.sources is None
        assert "sources" not in pkg.to_descriptor()

    def test_empty_licenses_collapses_to_none(
        self, contract_factory: type[ModelFactory]
    ):
        pkg = _make_package(contract_factory, licenses=[])
        assert pkg.licenses is None
        assert "licenses" not in pkg.to_descriptor()

    def test_non_empty_contributors_retained(
        self, contract_factory: type[ModelFactory]
    ):
        from crosscontract.contracts.contracts.metadata_models import Contributor

        pkg = _make_package(contract_factory, contributors=[Contributor(title="Jane")])
        assert pkg.contributors is not None
        assert "contributors" in pkg.to_descriptor()


class TestResourcesMinLength:
    def test_empty_resources_raises(self, contract_factory: type[ModelFactory]):
        with pytest.raises(ValidationError, match="resources"):
            CrossDataPackage(
                name="empty-package",
                title="Empty",
                description="No resources.",
                resources=[],
            )


class TestToFile:
    def test_writes_valid_json(self, contract_factory: type[ModelFactory], tmp_path):
        pkg = _make_package(contract_factory)
        out = tmp_path / "package.json"
        pkg.to_file(out)

        content = json.loads(out.read_text())
        assert content["profile"] == "data-package"
        assert content["name"] == "test-package"
        assert len(content["resources"]) == 1
        assert "schema" in content["resources"][0]
        assert "tableschema" not in content["resources"][0]

    def test_writes_valid_yaml(self, contract_factory: type[ModelFactory], tmp_path):
        pkg = _make_package(contract_factory)
        out = tmp_path / "package.yaml"
        pkg.to_file(out)

        with out.open() as f:
            content = yaml.safe_load(f)
        assert content["profile"] == "data-package"
        assert content["name"] == "test-package"
        assert len(content["resources"]) == 1
        assert "schema" in content["resources"][0]
        assert "tableschema" not in content["resources"][0]

    def test_writes_valid_yml_extension(
        self, contract_factory: type[ModelFactory], tmp_path
    ):
        pkg = _make_package(contract_factory)
        out = tmp_path / "package.yml"
        pkg.to_file(out)

        with out.open() as f:
            content = yaml.safe_load(f)
        assert content["profile"] == "data-package"

    def test_unsupported_extension_raises(
        self, contract_factory: type[ModelFactory], tmp_path
    ):
        pkg = _make_package(contract_factory)
        with pytest.raises(ValueError, match="Unsupported extension"):
            pkg.to_file(tmp_path / "package.toml")

    def test_accepts_string_path(self, contract_factory: type[ModelFactory], tmp_path):
        pkg = _make_package(contract_factory)
        out = str(tmp_path / "package.json")
        pkg.to_file(out)
        content = json.loads((tmp_path / "package.json").read_text())
        assert content["name"] == "test-package"
