from typing import TYPE_CHECKING, Any

from crosscontract import SubmissionContract

from .schemas import Submission, SubmissionContractEntryPayload

if TYPE_CHECKING:  # pragma: no cover
    from .submission_service import SubmissionContractService


class SubmissionContractResource:
    """A handle to a submission contract that exists on the CROSS platform."""

    def __init__(
        self,
        service: "SubmissionContractService",
        payload: SubmissionContractEntryPayload,
    ):
        """Initialise from a parsed server payload.

        Most callers should use :meth:`from_response` to parse a raw JSON dict;
        this constructor takes a pre-validated payload to keep tests direct.
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
        """Build a SubmissionContractResource from a raw server response dict."""
        payload = SubmissionContractEntryPayload.model_validate(response_json)
        return cls(service, payload)

    @property
    def name(self) -> str:
        return self._name

    @property
    def project_name(self) -> str:
        return self._project_name

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description

    @property
    def tags(self) -> list[str]:
        return self._tags

    @property
    def allow_submissions(self) -> bool:
        return self._allow_submissions

    @property
    def contract(self) -> SubmissionContract:
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
        """Set the allow_submissions flag through the service and
        update the local state.

        Args:
            allow (bool): The new value for the allow_submissions flag.
        """
        self._service.set_allow_submissions(self.name, allow)
        self._allow_submissions = allow

    def delete(self) -> None:
        """Delete the submission contract through the service."""
        self._service.delete(self.name)

    def refresh(self) -> None:
        """Re-fetch the submission contract from the service and update the
        local state."""
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
        """Fetch the list of submissions for this submission contract from the
        service."""
        return self._service.list_submissions(self.name)
