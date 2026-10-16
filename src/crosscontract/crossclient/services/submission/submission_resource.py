from typing import TYPE_CHECKING, Any

from crosscontract import SubmissionContract

from .schemas import Submission, SubmissionContractEntryPayload

if TYPE_CHECKING:  # pragma: no cover
    from .submission_service import SubmissionContractService


class SubmissionContractResource:
    """A handle to a submission contract that exists on the CROSS platform.

    Produced by the service's `create` and `get`; not constructed directly.
    Its properties are read-only and change only through its methods.
    """

    def __init__(
        self,
        service: "SubmissionContractService",
        payload: SubmissionContractEntryPayload,
    ):
        """Initialize from a parsed server payload.

        Use `from_response` to build a resource from a raw response dict.

        Args:
            service (SubmissionContractService): The service the resource
                delegates its methods to.
            payload (SubmissionContractEntryPayload): The parsed server response.

        Raises:
            pydantic.ValidationError: If `payload.contract` is not a valid
                `SubmissionContract`.
        """
        self._service = service
        self._name = payload.name
        self._project_name = payload.project_name
        self._title = payload.title
        self._description = payload.description
        self._tags = payload.tags
        self._allow_submissions = payload.allow_submissions
        self._contract = SubmissionContract.from_server(payload.contract)

    @classmethod
    def from_response(
        cls,
        service: "SubmissionContractService",
        response_json: dict[str, Any],
    ) -> "SubmissionContractResource":
        """Build a resource from a raw server response dict.

        Args:
            service (SubmissionContractService): The service the resource
                delegates its methods to.
            response_json (dict[str, Any]): The response body of a read of one
                submission contract.

        Returns:
            SubmissionContractResource: The resource.

        Raises:
            pydantic.ValidationError: If the response or its `contract` is
                malformed.
        """
        payload = SubmissionContractEntryPayload.model_validate(response_json)
        return cls(service, payload)

    @property
    def name(self) -> str:
        """
        Returns:
            str: The name of the submission contract.
        """
        return self._name

    @property
    def project_name(self) -> str:
        """
        Returns:
            str: The name of the project owning the submission contract.
        """
        return self._project_name

    @property
    def title(self) -> str:
        """
        Returns:
            str: The title of the submission contract.
        """
        return self._title

    @property
    def description(self) -> str:
        """
        Returns:
            str: The description of the submission contract.
        """
        return self._description

    @property
    def tags(self) -> list[str]:
        """
        Returns:
            list[str]: The tags of the submission contract.
        """
        return self._tags

    @property
    def allow_submissions(self) -> bool:
        """
        Returns:
            bool: Whether the owning project may currently upload submissions.
        """
        return self._allow_submissions

    @property
    def contract(self) -> SubmissionContract:
        """
        Returns:
            SubmissionContract: The stored submission contract.
        """
        return self._contract

    def __setattr__(self, name, value):
        # 1. Access the class to find the attribute definition
        # We use type(self) to avoid triggering infinite recursion or property getters
        attr = getattr(type(self), name, None)

        # 2. Check if the attribute is a property and if it has no setter
        if isinstance(attr, property) and attr.fset is None:
            raise AttributeError(
                "SubmissionContractResource is read-only. Use the methods to "
                "update properties."
            )

        # 3. If it's not a read-only property, allow the default behavior
        # This allows setting private variables like self._x = 10
        super().__setattr__(name, value)

    def __repr__(self) -> str:
        return (
            f"SubmissionContractResource(name={self.name}, "
            f"allow_submissions={self.allow_submissions})"
        )

    def set_allow_submissions(self, allow: bool) -> None:
        """Open or close the submission contract for submissions.

        Closing it stops new uploads; submissions already received are still
        processed. Setting the value it already has changes nothing.

        Args:
            allow (bool): `True` to open the submission contract, `False` to
                close it.
        """
        self._service.set_allow_submissions(self.name, allow)
        self._allow_submissions = allow

    def delete(self) -> None:
        """Delete the submission contract from the CROSS platform.

        The data contracts its targets name are not affected.
        """
        self._service.delete(self.name)

    def refresh(self) -> None:
        """Re-fetch the submission contract and replace the local state.

        Raises:
            ValueError: If the CROSS platform returns a submission contract of a
                different name.
        """
        remote = self._service.get(self.name)
        if remote.name != self.name:
            raise ValueError(
                f"Fetched contract name '{remote.name}' does not match "
                f"resource name '{self.name}'."
            )
        self._project_name = remote.project_name
        self._title = remote.title
        self._description = remote.description
        self._tags = remote.tags
        self._allow_submissions = remote.allow_submissions
        self._contract = SubmissionContract.from_server(remote.contract)

    def submissions(self) -> list[Submission]:
        """Fetch every submission of this submission contract, oldest first.

        Returns:
            list[Submission]: The submissions.
        """
        return self._service.list_submissions(self.name)
