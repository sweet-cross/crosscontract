from typing import TYPE_CHECKING

FilterValue = str | int | float | bool

if TYPE_CHECKING:  # pragma: no cover
    from ...crossclient import CrossClient


class SubmissionContractService:
    """Entry point for operations on submission contracts and their submissions."""

    _api_version_prefix = "/api/v1"

    def __init__(self, client: "CrossClient"):
        """Initialize the service.

        Args:
            client (CrossClient): The CrossClient instance to use for API calls.
        """
        self._client = client
