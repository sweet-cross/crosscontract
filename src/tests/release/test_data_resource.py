import pytest
from polyfactory.factories.pydantic_factory import ModelFactory

from crosscontract.release import CrossDataResource


class TestCrossDataResource:
    def test_from_contract(self, contract_factory: type[ModelFactory]):
        contract = contract_factory.build()
        path = "data/file.csv"
        data_resource = CrossDataResource.from_contract(contract, path)

        assert data_resource.path == path
        assert data_resource.format == "csv"
        assert data_resource.encoding == "utf-8"
        assert data_resource.profile == "tabular-data-resource"

    def test_profile_computation(self, contract_factory: type[ModelFactory]):
        # Test that the profile is computed correctly based on the format
        contract = contract_factory.build()
        csv_resource = CrossDataResource.from_contract(contract, "data/file.csv")
        assert csv_resource.profile == "tabular-data-resource"

        parquet_resource = CrossDataResource.from_contract(
            contract, "data/file.parquet", format="parquet"
        )
        assert parquet_resource.profile == "data-resource"

    def test_file_name_consistency_validation(
        self, contract_factory: type[ModelFactory]
    ):
        contract = contract_factory.build()
        with pytest.raises(ValueError, match="consistent with declared format 'csv'"):
            CrossDataResource.from_contract(contract, "data/file.txt")

        with pytest.raises(
            ValueError, match="consistent with declared format 'parquet'"
        ):
            CrossDataResource.from_contract(contract, "data/file.txt", format="parquet")

    def test_model_dump_uses_neutral_tableschema_key(
        self, contract_factory: type[ModelFactory]
    ):
        # The model itself stays release-agnostic: its default serialization keeps
        # the internal `tableschema` key, not the Frictionless `schema` wire-name.
        contract = contract_factory.build()
        resource = CrossDataResource.from_contract(contract, "data/file.csv")

        dumped = resource.model_dump()
        assert "tableschema" in dumped
        assert "schema" not in dumped

    def test_tableschema_round_trips_through_validation(
        self, contract_factory: type[ModelFactory]
    ):
        # Removing the serialization alias keeps dump -> validate symmetric: the
        # dumped `tableschema` key is the one validation accepts. `profile` is an
        # output-only computed field, so it is dropped before re-validating.
        contract = contract_factory.build()
        resource = CrossDataResource.from_contract(contract, "data/file.csv")

        dumped = resource.model_dump()
        dumped.pop("profile")
        restored = CrossDataResource.model_validate(dumped)

        assert restored.tableschema == resource.tableschema
        assert restored.path == resource.path

    def test_to_descriptor_emits_frictionless_schema_key(
        self, contract_factory: type[ModelFactory]
    ):
        # The Frictionless wire-name is applied in exactly one place: to_descriptor.
        contract = contract_factory.build()
        resource = CrossDataResource.from_contract(contract, "data/file.csv")

        descriptor = resource.to_descriptor()
        assert "schema" in descriptor
        assert "tableschema" not in descriptor

    def test_to_descriptor_schema_equals_model_tableschema(
        self, contract_factory: type[ModelFactory]
    ):
        # Renaming the key must not alter the schema content.
        contract = contract_factory.build()
        resource = CrossDataResource.from_contract(contract, "data/file.csv")

        descriptor = resource.to_descriptor()
        assert descriptor["schema"] == resource.model_dump(mode="json")["tableschema"]

    def test_to_descriptor_includes_resource_metadata(
        self, contract_factory: type[ModelFactory]
    ):
        # The descriptor is self-contained: file binding plus the derived profile.
        contract = contract_factory.build()
        resource = CrossDataResource.from_contract(
            contract, "data/file.parquet", format="parquet"
        )

        descriptor = resource.to_descriptor()
        assert descriptor["path"] == "data/file.parquet"
        assert descriptor["format"] == "parquet"
        assert descriptor["encoding"] == "utf-8"
        assert descriptor["profile"] == "data-resource"
        assert descriptor["name"] == contract.name
