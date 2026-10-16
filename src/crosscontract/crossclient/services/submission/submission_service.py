from typing import TYPE_CHECKING

FilterValue = str | int | float | bool

if TYPE_CHECKING:  # pragma: no cover
    from ...crossclient import CrossClient


class SubmissionContractService:
    """
    Entry point for operations on submission contracts.
    """

    _api_version_prefix = "/api/v1"

    def __init__(self, client: "CrossClient"):
        """Initialize the ContractService. The ContractService is responsible for
        managing submission contracts on the CROSS platform.

        It provides methods to create, retrieve, list, and delete submission
        contracts.

        Args:
            client (CrossClient): The CrossClient instance to use for API calls.
        """
        self._client = client
