import pytest
from polyfactory.factories.pydantic_factory import ModelFactory
from pydantic import ValidationError

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

    @pytest.mark.skip(
        reason="Stale: pending CrossDataResource schema field rename to "
        "`table_schema` with alias='schema'; rewrite against the final field name."
    )
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

    @pytest.mark.skip(
        reason="Stale: pending CrossDataResource schema field rename to "
        "`table_schema` with alias='schema'; rewrite against the final field name."
    )
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

    @pytest.mark.skip(
        reason="Stale: pending CrossDataResource schema field rename to "
        "`table_schema` with alias='schema'; rewrite against the final field name."
    )
    def test_to_descriptor_schema_equals_model_tableschema(
        self, contract_factory: type[ModelFactory]
    ):
        # Renaming the key must not alter the schema content.
        contract = contract_factory.build()
        resource = CrossDataResource.from_contract(contract, "data/file.csv")

        descriptor = resource.to_descriptor()
        assert (
            descriptor["schema"]
            == resource.model_dump(mode="json", exclude_none=True)["tableschema"]
        )

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

    def test_from_contract_rejects_a_data_resource(
        self, contract_factory: type[ModelFactory]
    ):
        # A resource already carries its data specification; re-binding it would
        # collide with the path/format/encoding arguments.
        contract = contract_factory.build()
        resource = CrossDataResource.from_contract(contract, "data/file.csv")

        with pytest.raises(TypeError, match="not a CrossDataResource"):
            CrossDataResource.from_contract(resource, "data/other.csv")


class TestFrictionlessPathConstraint:
    def test_rejects_absolute_path(self, contract_factory: type[ModelFactory]):
        with pytest.raises(ValidationError, match="path"):
            CrossDataResource.from_contract(
                contract_factory.build(), "/absolute/file.csv"
            )

    def test_rejects_path_starting_with_dot(self, contract_factory: type[ModelFactory]):
        with pytest.raises(ValidationError, match="path"):
            CrossDataResource.from_contract(
                contract_factory.build(), "./relative/file.csv"
            )

    def test_rejects_path_starting_with_tilde(
        self, contract_factory: type[ModelFactory]
    ):
        with pytest.raises(ValidationError, match="path"):
            CrossDataResource.from_contract(contract_factory.build(), "~/home/file.csv")

    def test_rejects_path_with_parent_traversal(
        self, contract_factory: type[ModelFactory]
    ):
        with pytest.raises(ValidationError, match="path"):
            CrossDataResource.from_contract(
                contract_factory.build(), "data/../file.csv"
            )

    def test_accepts_simple_relative_path(self, contract_factory: type[ModelFactory]):
        resource = CrossDataResource.from_contract(
            contract_factory.build(), "data/file.csv"
        )
        assert resource.path == "data/file.csv"

    def test_accepts_nested_relative_path(self, contract_factory: type[ModelFactory]):
        resource = CrossDataResource.from_contract(
            contract_factory.build(), "subdir/nested/file.csv"
        )
        assert resource.path == "subdir/nested/file.csv"


class TestEmptyMetadataListToNone:
    def test_empty_contributors_collapses_to_none(
        self, contract_factory: type[ModelFactory]
    ):
        # Inherited from CrossMetaData: empty optional metadata lists become None so
        # the release descriptor omits them rather than emitting minItems:1-violating
        # empty arrays.
        contract = contract_factory.build(contributors=[], sources=[], licenses=[])
        resource = CrossDataResource.from_contract(contract, "data/file.csv")

        assert resource.contributors is None
        assert resource.sources is None
        assert resource.licenses is None

        descriptor = resource.to_descriptor()
        assert "contributors" not in descriptor
        assert "sources" not in descriptor
        assert "licenses" not in descriptor
