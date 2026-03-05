from unittest.mock import patch

import httpx
import pytest
import respx

from crosscontract import CrossClient

# Mock Data
TEST_ENDPOINT = "https://api.example.com/data"


@respx.mock
def test_initial_authentication_success(client: CrossClient, login_url):
    """Test that the client authenticates lazily on the first request."""
    # Mock the login endpoint
    respx.post(login_url).mock(
        return_value=httpx.Response(200, json={"access_token": "token_123"})
    )
    # Mock the actual API endpoint
    respx.get(TEST_ENDPOINT).mock(
        return_value=httpx.Response(200, json={"data": "success"})
    )

    # Make the request
    response = client.get("/data")

    # Assertions
    assert response.status_code == 200
    assert response.json() == {"data": "success"}
    assert client._token == "token_123"
    assert respx.post(login_url).call_count == 1


@respx.mock
def test_authentication_failure_raises_error(client: CrossClient, login_url):
    """Test that invalid credentials raise an exception."""
    respx.post(login_url).mock(
        return_value=httpx.Response(401, json={"detail": "Invalid credentials"})
    )

    with pytest.raises(httpx.HTTPStatusError):
        client.get("/data")


@respx.mock
def test_token_refresh_flow(client: CrossClient, login_url):
    """
    Critical Test: Verify that a 401 triggers a re-auth and retry.

    Sequence we expect:
    1. First request -> 401 (Token expired)
    2. Client calls Login -> 200 (Get new token)
    3. Client retries request -> 200 (Success)
    """
    # We manually set a stale token to simulate a returning user
    client._token = "stale_token"
    client._client.headers["Authorization"] = "Bearer stale_token"
    # Define the mock behaviors
    login_route = respx.post(login_url).mock(
        return_value=httpx.Response(200, json={"access_token": "new_fresh_token"})
    )

    # We use a side_effect to return 401 first, then 200
    data_route = respx.get(TEST_ENDPOINT)
    data_route.side_effect = [
        httpx.Response(401),  # First call fails
        httpx.Response(200, json={"result": "recovered"}),  # Retry succeeds
    ]

    # Execute
    response = client.get("/data")

    # Assertions
    assert response.status_code == 200
    assert response.json() == {"result": "recovered"}

    # Check that we actually called login
    assert login_route.call_count == 1
    # Check that the client token was updated
    assert client._token == "new_fresh_token"
    # Check that the endpoint was called twice (initial fail + retry)
    assert data_route.call_count == 2


def test_context_manager():
    """Test that the context manager closes the client."""
    with patch("crosscontract.crossclient.crossclient.CrossClient.authenticate"):
        # Just ensure it doesn't crash
        with CrossClient("user", "pass", "https://api.example.com") as c:
            assert isinstance(c, CrossClient)

        # Verify underlying client is closed
        assert c._client.is_closed
        assert c._is_closed
        # using after close should raise error
        with pytest.raises(RuntimeError):
            c.get("/data")


def test_repr(client: CrossClient):
    """Test the __repr__ method of CrossClient."""
    repr_str = repr(client)
    assert "CrossClient" in repr_str
    assert client._username in repr_str
    assert client._base_url in repr_str


def test_del_closes_client():
    """Test that __del__ closes the client as a best-effort cleanup."""
    with patch("crosscontract.crossclient.crossclient.CrossClient.authenticate"):
        c = CrossClient("user", "pass", "https://api.example.com")
        assert not c._is_closed

        c.__del__()

        assert c._is_closed
        assert c._client.is_closed


def test_del_does_not_raise_on_already_closed():
    """Test that __del__ swallows exceptions if the client is already closed."""
    with patch("crosscontract.crossclient.crossclient.CrossClient.authenticate"):
        c = CrossClient("user", "pass", "https://api.example.com")
        c.close()

        # Should not raise even though already closed
        c.__del__()


def test_del_swallows_exception_from_close():
    """Test that __del__ suppresses exceptions raised by close()."""
    with patch("crosscontract.crossclient.crossclient.CrossClient.authenticate"):
        c = CrossClient("user", "pass", "https://api.example.com")

        with patch.object(c, "close", side_effect=RuntimeError("boom")):
            # Should not raise
            c.__del__()
