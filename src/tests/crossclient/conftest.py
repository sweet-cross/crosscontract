from unittest.mock import patch

import pytest
from polyfactory.factories.pydantic_factory import ModelFactory

from crosscontract.contracts import CrossContract, TableSchema
from crosscontract.crossclient import CrossClient
from crosscontract.crossclient.services.contract_service import ContractService

# Shared Constants
BASE_URL = "https://api.example.com"
LOGIN_URL = f"{BASE_URL}/user/auth/login"
USERNAME = "testuser"
PASSWORD = "secretpassword"


@pytest.fixture
def base_url():
    return BASE_URL


@pytest.fixture
def login_url():
    return LOGIN_URL


@pytest.fixture
def client():
    """Fixture to provide a fresh (unauthenticated) client."""
    with patch("crosscontract.crossclient.crossclient.CrossClient.authenticate"):
        return CrossClient(USERNAME, PASSWORD, BASE_URL)


@pytest.fixture
def service(auth_client):
    """Fixture to provide the ContractService using the authenticated client."""
    return ContractService(auth_client)


@pytest.fixture
def auth_client(client):
    """
    Fixture to provide a pre-authenticated client.
    This bypasses the actual login call by manually setting variable logic,
    which is sufficient for testing downstream services.
    """
    client._token = "token_123"
    client._client.headers["Authorization"] = "Bearer token_123"
    yield client


class CrossContractFactory(ModelFactory[CrossContract]):
    __model__ = CrossContract

    # OPTIONAL: If references cause noise, you can set defaults here
    # even while keeping the rest dynamic.
    @classmethod
    def tableschema(cls):
        # Force empty foreign keys to avoid 'validate_self_reference' issues entirely
        return TableSchema(fields=[{"name": "id", "type": "string"}], foreignKeys=[])


@pytest.fixture(scope="session")
def contract_factory() -> type[CrossContractFactory]:
    """
    Returns the Factory CLASS itself, allowing tests to call .build()
    with different overrides.
    """
    return CrossContractFactory
