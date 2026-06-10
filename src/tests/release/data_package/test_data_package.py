import json

import pytest
import yaml
from polyfactory.factories.pydantic_factory import ModelFactory

from crosscontract.release import CrossDataResource
from crosscontract.release.data_package.data_package import CrossDataPackage


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
        # contributors, sources, licenses are None — they must not appear in output
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
        from crosscontract.contracts.contracts.metadata_models import License

        pkg = _make_package(
            contract_factory,
            licenses=[License(name="CC-BY-4.0")],
        )
        descriptor = pkg.to_descriptor()
        assert "licenses" in descriptor
        assert descriptor["licenses"][0]["name"] == "CC-BY-4.0"

    def test_resource_count_matches(self, contract_factory: type[ModelFactory]):
        r1 = CrossDataResource.from_contract(contract_factory.build(), "data/first.csv")
        r2 = CrossDataResource.from_contract(
            contract_factory.build(), "data/second.csv"
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
        # model_dump must still carry tableschema (stay neutral/round-trippable)
        pkg = _make_package(contract_factory)
        raw = pkg.model_dump()
        for resource in raw["resources"]:
            assert "tableschema" in resource
            assert "schema" not in resource


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
