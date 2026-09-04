from crosscontract import CrossClient
from crosscontract.crossclient.services import CrossContractResolver


class CrossSubmitter:
    """The data provider's entry point to the CROSS platform.

    The write-side counterpart of `CrossRegistry`, constructed the same way and
    building its own contract resolver so a submission can be validated against
    the contracts it names.

    Validation performed here is advisory: it sees only what the calling user
    may read, and the platform re-validates on ingest.
    """

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        client: CrossClient | None = None,
    ):
        """Initialize the submitter from either a client or username/password.

        Args:
            username (str | None, optional): The username or email to connect to
                the CROSS platform. Ignored when `client` is given. Defaults to
                `None`.
            password (str | None, optional): The password to connect to the CROSS
                platform. Ignored when `client` is given. Defaults to `None`.
            client (CrossClient | None, optional): An existing client. When given
                it is used as-is, otherwise a new one is built from `username`
                and `password`. Defaults to `None`.

        Raises:
            ValueError: If no `client` is given and `username` or `password` is
                missing.
        """
        if client is None:
            if username is None or password is None:
                raise ValueError(
                    "Either a CrossClient instance or both username and password must "
                    "be provided."
                )
            client = CrossClient(username=username, password=password)

        self._client = client
        self._resolver = CrossContractResolver(client.contracts)

    def submit(self):
        """Submit a delivered bundle to the CROSS platform.

        Raises:
            NotImplementedError: Always. The CROSS platform does not yet expose
                a submission endpoint.
        """
        raise NotImplementedError("The submit method is not yet implemented.")
