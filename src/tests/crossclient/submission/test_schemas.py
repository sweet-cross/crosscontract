from datetime import datetime
from uuid import UUID

import pytest
from pydantic import ValidationError as PydanticValidationError

from crosscontract.contracts.submission import SubmissionContract
from crosscontract.crossclient.services.submission.schemas import (
    Submission,
    SubmissionContractEntryPayload,
)

from .conftest import entry_response, submission_response


class TestPayload:
    def test_parses_entry_response(self, contract: SubmissionContract):
        """The payload carries every field of a `SubmissionContractEntryResponse`."""
        payload = SubmissionContractEntryPayload.model_validate(
            entry_response(contract, allow_submissions=False)
        )
        assert payload.name == "submission3"
        assert payload.project_name == "project1"
        assert payload.title == "Test Submission"
        assert payload.description == contract.description
        assert payload.allow_submissions is False
        assert payload.contract == contract.model_dump(mode="json")

    def test_missing_contract_is_rejected(self, contract: SubmissionContract):
        """A metadata-only response, as `create` and `overview` return, is rejected."""
        response = entry_response(contract)
        del response["contract"]
        with pytest.raises(PydanticValidationError):
            SubmissionContractEntryPayload.model_validate(response)


class TestSubmission:
    def test_parses_submission_response(self):
        """A `SubmissionResponse` dict parses into typed fields."""
        submission = Submission.model_validate(submission_response())
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
        assert Submission.model_validate(submission_response(state)).state == state

    def test_rejects_unknown_state(self):
        """A state outside `SubmissionState` is rejected."""
        with pytest.raises(PydanticValidationError):
            Submission.model_validate(submission_response("pending"))
