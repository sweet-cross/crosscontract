import pytest
from polyfactory.factories.pydantic_factory import ModelFactory

from crosscontract.contracts import CrossContract, TableSchema
from crosscontract.contracts.contracts.metadata_models import License


class CrossContractFactory(ModelFactory[CrossContract]):
    __model__ = CrossContract

    # set the general contract relying on the default TableSchema
    contract_type = "General"

    # Pinned to a Frictionless-legal lowercase name (see `CONTRACT_NAME_PATTERN`)
    # so that CrossDataResource can be constructed from any factory build.
    name = "my-contract"

    @classmethod
    def tableschema(cls):
        # Force empty foreign keys to avoid 'validate_self_reference' issues entirely
        return TableSchema(fields=[{"name": "id", "type": "string"}], foreignKeys=[])

    @classmethod
    def licenses(cls) -> list[License] | None:
        """
        Overrides the 'licenses' field to handle the custom Pydantic validation
        for the nested License objects.
        """
        return [
            License(
                title="Creative Commons Attribution 4.0",
                path="https://creativecommons.org/licenses/by/4.0/",
            )
        ]


@pytest.fixture(scope="session")
def contract_factory() -> type[CrossContractFactory]:
    """
    Returns the Factory CLASS itself, allowing tests to call .build()
    with different overrides.
    """
    return CrossContractFactory
