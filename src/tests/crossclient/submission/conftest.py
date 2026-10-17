from crosscontract.contracts.submission import SubmissionContract


def metadata_response(
    contract: SubmissionContract,
    allow_submissions: bool = True,
    project_name: str | None = None,
) -> dict:
    """Build a server-style `SubmissionContractMetaDataResponse` dict."""
    return {
        "name": contract.name,
        "project_name": project_name or contract.project_name,
        "title": contract.title,
        "description": contract.description,
        "tags": list(contract.tags or []),
        "allow_submissions": allow_submissions,
    }


def entry_response(
    contract: SubmissionContract,
    allow_submissions: bool = True,
    project_name: str | None = None,
) -> dict:
    """Build a server-style `SubmissionContractEntryResponse` dict."""
    return {
        **metadata_response(contract, allow_submissions, project_name),
        "contract": contract.model_dump(mode="json"),
    }


def submission_response(state: str = "received") -> dict:
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
