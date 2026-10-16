from typing import TYPE_CHECKING
from uuid import UUID

import pandas as pd

from crosscontract.contracts.submission import SubmissionContract

from ...exceptions import raise_from_response
from .schemas import Submission
from .submission_resource import SubmissionContractResource

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
        self._route = f"{self._client._base_url}{self._api_version_prefix}/submission"

    def create(self, contract: SubmissionContract) -> SubmissionContractResource:
        """Create a submission contract on the CROSS platform.

        Every target of the contract must name an existing, active data contract.

        Args:
            contract (SubmissionContract): The submission contract to create.

        Returns:
            SubmissionContractResource: The created submission contract.

        Raises:
            CrossClientError: If the request fails, e.g. `PermissionDeniedError`
                if the caller is not a manager of the contract's project, or
                `ConflictError` if the name is taken or a target names a data
                contract that is missing or not active.
        """
        response = self._client.post(
            f"{self._route}/contract", json=contract.to_server()
        )
        raise_from_response(response)
        return self.get(contract.name)

    def get(self, name: str) -> SubmissionContractResource:
        """Get a submission contract by name.

        Args:
            name (str): The name of the submission contract.

        Returns:
            SubmissionContractResource: The submission contract.

        Raises:
            CrossClientError: If the request fails, e.g. `ResourceNotFoundError`
                if no submission contract of that name exists.
        """
        response = self._client.get(f"{self._route}/contract/{name}")
        raise_from_response(response)
        return SubmissionContractResource.from_response(self, response.json())

    def overview(self, project_name: str) -> pd.DataFrame:
        """Get an overview of a project's submission contracts.

        Args:
            project_name (str): The name of the project.

        Returns:
            pd.DataFrame: One row per submission contract, with the columns
                `name`, `project_name`, `title`, `description`, `tags`, and
                `allow_submissions`.

        Raises:
            CrossClientError: If the request fails, e.g. `ResourceNotFoundError`
                if the project does not exist.
        """
        response = self._client.get(
            f"{self._route}/contract", params={"project_name": project_name}
        )
        raise_from_response(response)
        return pd.DataFrame(response.json()["items"])

    def delete(self, name: str) -> None:
        """Delete a submission contract by name.

        The data contracts its targets name are not affected.

        Args:
            name (str): The name of the submission contract.

        Raises:
            CrossClientError: If the request fails, e.g. `ResourceNotFoundError`
                if no submission contract of that name exists.
        """
        response = self._client.delete(f"{self._route}/contract/{name}")
        raise_from_response(response)

    def set_allow_submissions(self, name: str, allow: bool) -> None:
        """Open or close a submission contract for submissions.

        Closing it stops new uploads; submissions already received are still
        processed. Setting the value it already has changes nothing.

        Args:
            name (str): The name of the submission contract.
            allow (bool): `True` to open the submission contract, `False` to
                close it.

        Raises:
            CrossClientError: If the request fails, e.g. `PermissionDeniedError`
                if the caller is not a manager of the contract's project.
        """
        response = self._client.request(
            "PUT",
            f"{self._route}/contract/{name}/allow-submissions",
            json={"allow_submissions": allow},
        )
        raise_from_response(response)

    def get_submission(self, uuid: UUID | str) -> Submission:
        """Get a submission by its uuid, e.g. to follow its processing state.

        Args:
            uuid (UUID | str): The uuid of the submission.

        Returns:
            Submission: The submission.

        Raises:
            CrossClientError: If the request fails, e.g. `ResourceNotFoundError`
                if no submission with that uuid exists.
        """
        response = self._client.get(f"{self._route}/{uuid}")
        raise_from_response(response)
        return Submission.model_validate(response.json())

    def list_submissions(self, name: str) -> list[Submission]:
        """List every submission of a submission contract, oldest first.

        Args:
            name (str): The name of the submission contract.

        Returns:
            list[Submission]: The submissions.

        Raises:
            CrossClientError: If the request fails, e.g. `ResourceNotFoundError`
                if no submission contract of that name exists.
        """
        response = self._client.get(f"{self._route}/contract/{name}/data")
        raise_from_response(response)
        return [Submission.model_validate(item) for item in response.json()["items"]]
