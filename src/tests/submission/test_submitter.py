from unittest.mock import patch

import pytest

from crosscontract import CrossClient
from crosscontract.crossclient.services import CrossContractResolver
from crosscontract.submission.submitter import CrossSubmitter

USERNAME = "testuser"
PASSWORD = "secretpassword"


@pytest.fixture
def client() -> CrossClient:
    """A client whose construction does not reach the platform."""
    with patch("crosscontract.crossclient.crossclient.CrossClient.authenticate"):
        return CrossClient(USERNAME, PASSWORD)


class TestConstruction:
    def test_credentials_build_a_client(self):
        with patch("crosscontract.crossclient.crossclient.CrossClient.authenticate"):
            submitter = CrossSubmitter(username=USERNAME, password=PASSWORD)
        assert isinstance(submitter._client, CrossClient)

    def test_given_client_is_used_as_is(self, client):
        submitter = CrossSubmitter(client=client)
        assert submitter._client is client

    def test_client_wins_over_credentials(self, client):
        """No second client is built when one is handed in."""
        submitter = CrossSubmitter(username="other", password="other", client=client)
        assert submitter._client is client

    @pytest.mark.parametrize(
        "kwargs",
        [{}, {"username": USERNAME}, {"password": PASSWORD}],
        ids=["nothing", "username_only", "password_only"],
    )
    def test_incomplete_credentials_raise(self, kwargs):
        with pytest.raises(ValueError):
            CrossSubmitter(**kwargs)

    def test_resolver_reads_through_the_client_contracts(self, client):
        submitter = CrossSubmitter(client=client)
        assert isinstance(submitter._resolver, CrossContractResolver)
        assert submitter._resolver._service is client.contracts

    def test_resolver_is_not_a_constructor_parameter(self, client):
        with pytest.raises(TypeError):
            CrossSubmitter(client=client, resolver=object())


class TestSubmit:
    def test_submit_is_an_honest_stub(self, client):
        submitter = CrossSubmitter(client=client)
        with pytest.raises(NotImplementedError):
            submitter.submit()
