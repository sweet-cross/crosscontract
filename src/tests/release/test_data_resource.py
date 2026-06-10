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
