import httpx

from .services import ContractService


class CrossClient:
    def __init__(
        self,
        username: str,
        password: str,
        base_url: str,
        verify: bool = True,
    ) -> None:
        """Initialize the client with authentication.

        Args:
            username (str): The username for authentication.
            password (str): The password for authentication.
            base_url (str): If provided, use this domain instead of the default
                BASE_URL. The debug option is ignored if base_url is set.
                The domain must include the protocol (e.g., http:// or https://).
                Example: "http://example.com/"
            verify (bool): Whether to verify SSL certificates.
                Defaults to True.

        Returns:
            CrossClient: An instance of the authenticated client.
        """
        self._base_url = base_url
        self._username = username
        self._password = password
        self._verify = verify
        self._token = None

        # Create the client
        timeout = httpx.Timeout(10.0, connect=30.0, read=60.0, write=None)
        limits = httpx.Limits(max_connections=5, max_keepalive_connections=5)
        self._client = httpx.Client(
            base_url=self._base_url,
            verify=verify,
            timeout=timeout,
            limits=limits,
        )
        self._is_closed = False

        # ---- include services ----
        self.contracts: ContractService = ContractService(client=self)

        # authenticate upon initialization
        self.authenticate()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        """Close the HTTPX client."""
        self._client.close()
        self._is_closed = True

    def __repr__(self):
        return f"CrossClient(base_url={self._base_url}, username={self._username})"

    def authenticate(self) -> str:
        """Authenticate with the server and retrieve an access token.

        Returns:
            str: The authentication token.
        """
        response = self._client.post(
            "/user/auth/login",
            data={"username": self._username, "password": self._password},
        )
        response.raise_for_status()  # Raise an error for bad responses
        token = response.json().get("access_token", "")
        self._token = token
        self._client.headers["Authorization"] = f"Bearer {self._token}"
        return token

    def request(self, method: str, endpoint: str, **kwargs: dict) -> httpx.Response:
        """Send an HTTP request to the specified endpoint.

        Args:
            method (str): The HTTP method (e.g., 'GET', 'POST').
            endpoint (str): The API endpoint to send the request to.
            **kwargs: Additional arguments to pass to the request.

        Returns:
            httpx.Response: The response from the server.
        """
        if self._is_closed:
            raise RuntimeError(
                "Attempted to make a request with a closed CrossClient. Ensure you "
                "are performing all operations within the 'with' context block."
            )
        if not self._token:
            self.authenticate()
        response = self._client.request(method, endpoint, **kwargs)

        # try to get a new token if unauthorized
        if response.status_code == 401:
            # Token expired: Refresh and retry
            self.authenticate()

            # Re-issue the request with the new header (handled by self._client update)
            # We must recreate the request to pick up the new headers from the
            # client state
            response = self._client.request(method, endpoint, **kwargs)
        return response

    def post(self, endpoint: str, json: dict | None = None, **kwargs) -> httpx.Response:
        """Send a POST request to the specified endpoint."""
        return self.request("POST", endpoint, json=json, **kwargs)  # pragma: no cover

    def delete(self, endpoint: str, **kwargs) -> httpx.Response:
        """Send a DELETE request to the specified endpoint."""
        return self.request("DELETE", endpoint, **kwargs)  # pragma: no cover

    def get(self, endpoint: str, **kwargs) -> httpx.Response:
        """Send a GET request to the specified endpoint."""
        return self.request("GET", endpoint, **kwargs)  # pragma: no cover

    def patch(
        self, endpoint: str, json: dict | None = None, **kwargs
    ) -> httpx.Response:
        """Send a PATCH request to the specified endpoint."""
        return self.request("PATCH", endpoint, json=json, **kwargs)  # pragma: no cover
