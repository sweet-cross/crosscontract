from unittest.mock import Mock

import pandas as pd
import pytest

from crosscontract import CrossContract
from crosscontract.contracts import ContractResolver
from crosscontract.crossclient.exceptions.exceptions import (
    PermissionDeniedError,
    ResourceNotFoundError,
    ServerError,
)
from crosscontract.crossclient.services.contract_service import ContractService
from crosscontract.crossclient.services.resolver import ClientContractResolver


def _contract(name: str = "region") -> CrossContract:
    return CrossContract(
        name=name,
        title="t",
        description="d",
        contract_type="General",
        tableschema={
            "primaryKey": ["id"],
            "fields": [
                {"name": "id", "type": "integer"},
                {"name": "value", "type": "number"},
            ],
        },
    )


@pytest.fixture
def resolver(service: ContractService) -> ClientContractResolver:
    return ClientContractResolver(service)


class TestResolve:
    def test_returns_the_contract(self, resolver: ClientContractResolver):
        """A known name gives back the contract behind the resource."""
        contract = _contract()
        resolver._service.get = Mock(return_value=Mock(contract=contract))

        assert resolver.resolve("region") is contract
        resolver._service.get.assert_called_once_with("region")

    def test_unknown_name_gives_none(self, resolver: ClientContractResolver):
        """A missing contract is an answer, not a failure."""
        resolver._service.get = Mock(side_effect=ResourceNotFoundError())

        assert resolver.resolve("nope") is None

    @pytest.mark.parametrize("error", [PermissionDeniedError, ServerError])
    def test_other_failures_propagate(
        self, resolver: ClientContractResolver, error: type[Exception]
    ):
        """Only 'not found' becomes None.

        Swallowing anything else would report a contract as missing when the
        platform merely refused or broke, and reference validation would then
        blame the contract rather than the request.
        """
        resolver._service.get = Mock(side_effect=error())

        with pytest.raises(error):
            resolver.resolve("region")


class TestGetData:
    def test_forwards_to_the_service(self, resolver: ClientContractResolver):
        expected = pd.DataFrame({"id": [1, 2]})
        resolver._service._get_data = Mock(return_value=expected)

        result = resolver.get_data("region", ["id"])

        assert result is expected
        resolver._service._get_data.assert_called_once_with(
            "region", columns=["id"], unique=True
        )

    def test_unique_is_forwarded_when_overridden(
        self, resolver: ClientContractResolver
    ):
        """The default assertion above also passes if the flag is dropped."""
        resolver._service._get_data = Mock(return_value=pd.DataFrame({"id": [1]}))

        resolver.get_data("region", ["id"], unique=False)

        resolver._service._get_data.assert_called_once_with(
            "region", columns=["id"], unique=False
        )

    def test_platform_errors_propagate(self, resolver: ClientContractResolver):
        """Unlike `resolve`, a missing contract here is not an answer.

        An empty frame would mean the referenced table exists and holds no rows,
        which fails every referring row — so a missing contract must not be
        turned into one.
        """
        resolver._service._get_data = Mock(side_effect=ResourceNotFoundError())

        with pytest.raises(ResourceNotFoundError):
            resolver.get_data("nope", ["id"])


def test_satisfies_the_protocol(resolver: ClientContractResolver):
    assert isinstance(resolver, ContractResolver)
