from datetime import datetime
from unittest.mock import Mock
from uuid import UUID

import pytest
from pydantic import ValidationError as PydanticValidationError

from crosscontract.contracts.submission import SubmissionContract
from crosscontract.crossclient.services.submission.schemas import (
    Submission,
    SubmissionContractEntryPayload,
)
from crosscontract.crossclient.services.submission.submission_resource import (
    SubmissionContractResource,
)


def _response_dict(
    contract: SubmissionContract,
    allow_submissions: bool = True,
    project_name: str | None = None,
) -> dict:
    """Build a server-style `SubmissionContractEntryResponse` dict."""
    return {
        "name": contract.name,
        "project_name": project_name or contract.project_name,
        "title": contract.title,
        "description": contract.description,
        "tags": list(contract.tags or []),
        "allow_submissions": allow_submissions,
        "contract": contract.model_dump(mode="json"),
    }


def _submission_dict(state: str = "received") -> dict:
    """Build a server-style `SubmissionResponse` dict."""
    return {
        "uuid": "8f2b7c1e-3a4d-4e5f-9a6b-7c8d9e0f1a2b",
        "submission_contract_name": "submission3",
        "project_name": "project1",
        "submitted_by": "alice",
        "original_filename": "bundle.parquet",
        "size": 1024,
        "hash": "ab" * 32,
        "state": state,
        "created_at": "2026-10-16T12:00:00Z",
    }


@pytest.fixture
def service() -> Mock:
    """A stand-in for the `SubmissionService` the resource delegates to."""
    return Mock()


@pytest.fixture
def resource(service: Mock, contract: SubmissionContract) -> SubmissionContractResource:
    """A resource built from the shared `SubmissionContract` fixture."""
    return SubmissionContractResource.from_response(service, _response_dict(contract))


class TestPayload:
    def test_parses_entry_response(self, contract: SubmissionContract):
        """The payload carries every field of a `SubmissionContractEntryResponse`."""
        payload = SubmissionContractEntryPayload.model_validate(
            _response_dict(contract, allow_submissions=False)
        )
        assert payload.name == "submission3"
        assert payload.project_name == "project1"
        assert payload.title == "Test Submission"
        assert payload.description == contract.description
        assert payload.allow_submissions is False
        assert payload.contract == contract.model_dump(mode="json")

    def test_missing_contract_is_rejected(self, contract: SubmissionContract):
        """A metadata-only response, as `create` and `overview` return, is rejected."""
        response = _response_dict(contract)
        del response["contract"]
        with pytest.raises(PydanticValidationError):
            SubmissionContractEntryPayload.model_validate(response)


class TestFromResponse:
    def test_builds_resource(self, service: Mock, contract: SubmissionContract):
        """from_response populates every property and parses the contract."""
        resource = SubmissionContractResource.from_response(
            service, _response_dict(contract, allow_submissions=False)
        )
        assert resource.name == "submission3"
        assert resource.project_name == "project1"
        assert resource.allow_submissions is False
        assert isinstance(resource.contract, SubmissionContract)
        assert resource.contract == contract

    def test_malformed_response(self, service: Mock):
        """from_response surfaces a validation error if the payload is malformed."""
        with pytest.raises(PydanticValidationError):
            SubmissionContractResource.from_response(
                service, {"name": "x", "project_name": "p"}
            )

    def test_invalid_contract(self, service: Mock, contract: SubmissionContract):
        """A `contract` that is not a valid `SubmissionContract` is rejected."""
        response = _response_dict(contract)
        del response["contract"]["extraction"]
        with pytest.raises(PydanticValidationError):
            SubmissionContractResource.from_response(service, response)

    def test_representation(self, resource: SubmissionContractResource):
        """The repr names the class and the submission contract."""
        repr_str = repr(resource)
        assert "SubmissionContractResource" in repr_str
        assert "submission3" in repr_str


class TestPublicSurface:
    @pytest.mark.parametrize(
        "attribute, value",
        [
            ("name", "other"),
            ("contract", None),
            ("project_name", "other"),
            ("allow_submissions", False),
        ],
    )
    def test_property_is_read_only(
        self, resource: SubmissionContractResource, attribute: str, value: object
    ):
        """Assigning to a property raises instead of changing local state."""
        with pytest.raises(AttributeError):
            setattr(resource, attribute, value)

    @pytest.mark.parametrize(
        "prefix", ["validate", "submit", "upload", "add_data", "_submit_data"]
    )
    def test_no_bundle_method(self, resource: SubmissionContractResource, prefix: str):
        """The resource neither validates, submits nor uploads bundles."""
        assert [name for name in dir(resource) if name.startswith(prefix)] == []


class TestServiceDelegation:
    @pytest.mark.parametrize("allow", [False, True])
    def test_set_allow_submissions_updates_flag(
        self, service: Mock, contract: SubmissionContract, allow: bool
    ):
        """The service is called with the name and the value, which is then kept."""
        resource = SubmissionContractResource.from_response(
            service, _response_dict(contract, allow_submissions=not allow)
        )
        resource.set_allow_submissions(allow)
        service.set_allow_submissions.assert_called_once_with("submission3", allow)
        assert resource.allow_submissions is allow

    def test_set_allow_submissions_failure_keeps_flag(
        self, service: Mock, resource: SubmissionContractResource
    ):
        """If the service raises, the local flag is left as it was."""
        service.set_allow_submissions.side_effect = RuntimeError("server said no")
        with pytest.raises(RuntimeError, match="server said no"):
            resource.set_allow_submissions(False)
        assert resource.allow_submissions is True

    def test_delete(self, service: Mock, resource: SubmissionContractResource):
        """delete() deletes the submission contract by name through the service."""
        resource.delete()
        service.delete.assert_called_once_with("submission3")

    def test_refresh_replaces_state(self, service: Mock, contract: SubmissionContract):
        """refresh() re-fetches by name and replaces contract, project and flag."""
        resource = SubmissionContractResource.from_response(
            service, _response_dict(contract, allow_submissions=True)
        )
        updated_contract = contract.model_copy(update={"title": "New title"})
        service.get.return_value = SubmissionContractResource.from_response(
            service,
            _response_dict(
                updated_contract, allow_submissions=False, project_name="project2"
            ),
        )

        resource.refresh()

        service.get.assert_called_once_with("submission3")
        assert resource.contract.title == "New title"
        assert resource.project_name == "project2"
        assert resource.allow_submissions is False

    def test_submissions(self, service: Mock, resource: SubmissionContractResource):
        """submissions() returns what the service lists for this contract."""
        submissions = [Submission.model_validate(_submission_dict())]
        service.get_submissions.return_value = submissions

        assert resource.submissions() == submissions
        service.get_submissions.assert_called_once_with("submission3")


class TestSubmission:
    def test_parses_submission_response(self):
        """A `SubmissionResponse` dict parses into typed fields."""
        submission = Submission.model_validate(_submission_dict())
        assert submission.uuid == UUID("8f2b7c1e-3a4d-4e5f-9a6b-7c8d9e0f1a2b")
        assert submission.submission_contract_name == "submission3"
        assert submission.project_name == "project1"
        assert submission.submitted_by == "alice"
        assert submission.original_filename == "bundle.parquet"
        assert submission.size == 1024
        assert submission.hash == "ab" * 32
        assert submission.state == "received"
        assert isinstance(submission.created_at, datetime)

    @pytest.mark.parametrize(
        "state",
        ["received", "processing", "current", "superseded", "rejected", "failed"],
    )
    def test_accepts_every_state(self, state: str):
        """Every state the server reports is accepted."""
        assert Submission.model_validate(_submission_dict(state)).state == state

    def test_rejects_unknown_state(self):
        """A state outside `SubmissionState` is rejected."""
        with pytest.raises(PydanticValidationError):
            Submission.model_validate(_submission_dict("pending"))
