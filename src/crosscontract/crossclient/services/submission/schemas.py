from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

SubmissionState = Literal[
    "received", "processing", "current", "superseded", "rejected", "failed"
]


class SubmissionContractEntryPayload(BaseModel):
    """A submission contract as the CROSS platform returns it when read by name.

    Carries the overview fields and, under `contract`, the stored submission
    contract as a raw dict.
    """

    name: str
    project_name: str
    title: str
    description: str
    tags: list[str]
    allow_submissions: bool
    contract: dict[str, Any]


class Submission(BaseModel):
    """A submission on the CROSS platform: what was uploaded, by whom, and its state.

    Holds metadata only, not the uploaded file. `state` is `received` right
    after the upload, `processing` while the platform works on it, and ends as
    `current` (valid and stored), `rejected` (invalid, nothing stored) or
    `failed` (a platform error, nothing stored). A `current` submission becomes
    `superseded` once a newer submission replaces its data.
    """

    uuid: UUID = Field(..., description="The public identifier of the submission")
    submission_contract_name: str = Field(
        ...,
        description="The name of the submission contract the bundle was submitted for",
    )
    project_name: str = Field(
        ...,
        description="The name of the project owning the submission contract",
    )
    submitted_by: str = Field(
        ...,
        description="The username of the submitter",
    )
    original_filename: str = Field(
        ..., description="The file name as sent by the client"
    )
    size: int = Field(..., description="The size of the uploaded file in bytes")
    hash: str = Field(..., description="The SHA-256 hex digest of the uploaded file")
    state: SubmissionState = Field(
        ..., description="The processing state of the submission"
    )
    created_at: datetime = Field(..., description="When the submission was received")
