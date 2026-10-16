from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

SubmissionState = Literal[
    "received", "processing", "current", "superseded", "rejected", "failed"
]


class SubmissionContractEntryPayload(BaseModel):
    """Client-side mirror of the server's `SubmissionContractEntryResponse`.

    Centralizing the shape here gives us validation at the API boundary and a
    single place to adjust if the server response evolves.
    """

    name: str
    project_name: str
    title: str
    description: str
    tags: list[str]
    allow_submissions: bool
    contract: dict[str, Any]


class Submission(BaseModel):
    """Metadata of a Submission: what was uploaded, by whom, and its state.

    Returned when a bundle is accepted for processing and when a Submission is
    read back to follow its state. The stored files are not part of it.
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
