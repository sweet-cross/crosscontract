import io
import json
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default

import httpx
import pandas as pd
import pytest
import respx

from crosscontract.contracts.submission import SubmissionContract
from crosscontract.crossclient import CrossClient
from crosscontract.crossclient.services.submission.schemas import Submission
from crosscontract.crossclient.services.submission.submission_resource import (
    SubmissionContractResource,
)
from crosscontract.crossclient.services.submission.submission_service import (
    SubmissionContractService,
)
from crosscontract.exceptions import (
    ConflictError,
    PermissionDeniedError,
    ResourceNotFoundError,
)

from .conftest import entry_response, metadata_response, submission_response

SUBMISSION_URL = "https://api.example.com/api/v1/submission"
CONTRACT_URL = f"{SUBMISSION_URL}/contract"
SUBMISSION_UUID = "8f2b7c1e-3a4d-4e5f-9a6b-7c8d9e0f1a2b"


@pytest.fixture
def service(auth_client: CrossClient) -> SubmissionContractService:
    """A `SubmissionContractService` on the pre-authenticated client."""
    return SubmissionContractService(auth_client)


def page(items: list[dict]) -> dict:
    """Wrap items in the server's `Page` envelope, as returned without `limit`."""
    return {
        "items": items,
        "total": len(items),
        "skip": 0,
        "limit": None,
        "has_next": False,
    }


class TestCreate:
    @respx.mock
    def test_posts_then_gets(
        self, service: SubmissionContractService, contract: SubmissionContract
    ):
        """create() posts the contract, then reads it back by name."""
        respx.post(CONTRACT_URL).respond(201, json=metadata_response(contract))
        respx.get(f"{CONTRACT_URL}/{contract.name}").respond(
            200, json=entry_response(contract)
        )

        service.create(contract)

        assert [call.request.method for call in respx.calls] == ["POST", "GET"]
        assert json.loads(respx.calls[0].request.content)["name"] == contract.name

    @respx.mock
    def test_resource_reflects_get(
        self, service: SubmissionContractService, contract: SubmissionContract
    ):
        """The returned resource is built from the GET, not the POST response."""
        respx.post(CONTRACT_URL).respond(
            201, json=metadata_response(contract, allow_submissions=False)
        )
        respx.get(f"{CONTRACT_URL}/{contract.name}").respond(
            200, json=entry_response(contract, allow_submissions=True)
        )

        resource = service.create(contract)

        assert isinstance(resource, SubmissionContractResource)
        assert resource.name == contract.name
        assert resource.allow_submissions is True
        assert resource.contract == contract

    @respx.mock
    def test_failed_post_skips_get(
        self, service: SubmissionContractService, contract: SubmissionContract
    ):
        """A rejected POST raises and is not followed by a GET."""
        respx.post(CONTRACT_URL).respond(403, json={"detail": "Not a manager"})
        get_route = respx.get(f"{CONTRACT_URL}/{contract.name}")

        with pytest.raises(PermissionDeniedError):
            service.create(contract)

        assert not get_route.called


class TestContractEndpoints:
    @respx.mock
    def test_get(
        self, service: SubmissionContractService, contract: SubmissionContract
    ):
        """get() reads the submission contract by name into a resource."""
        respx.get(f"{CONTRACT_URL}/{contract.name}").respond(
            200, json=entry_response(contract, allow_submissions=False)
        )

        resource = service.get(contract.name)

        assert isinstance(resource, SubmissionContractResource)
        assert resource.project_name == "project1"
        assert resource.allow_submissions is False
        assert resource.contract == contract

    @respx.mock
    def test_overview(
        self, service: SubmissionContractService, contract: SubmissionContract
    ):
        """overview() lists a project's submission contracts as a DataFrame."""
        route = respx.get(CONTRACT_URL).respond(
            200, json=page([metadata_response(contract)])
        )

        df = service.overview("project1")

        params = route.calls.last.request.url.params
        assert params.get("project_name") == "project1"
        assert "limit" not in params
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == list(metadata_response(contract))
        assert df["name"].tolist() == [contract.name]

    @respx.mock
    def test_delete(self, service: SubmissionContractService):
        """delete() deletes the submission contract by name."""
        route = respx.delete(f"{CONTRACT_URL}/submission3").respond(204)

        assert service.delete("submission3") is None
        assert route.called

    @pytest.mark.parametrize("allow", [False, True])
    @respx.mock
    def test_set_allow_submissions(
        self,
        service: SubmissionContractService,
        contract: SubmissionContract,
        allow: bool,
    ):
        """set_allow_submissions() sends exactly the flag to set."""
        route = respx.put(f"{CONTRACT_URL}/{contract.name}/allow-submissions").respond(
            200, json=metadata_response(contract, allow_submissions=allow)
        )

        assert service.set_allow_submissions(contract.name, allow) is None
        assert json.loads(route.calls.last.request.content) == {
            "allow_submissions": allow
        }


class TestSubmissionEndpoints:
    @respx.mock
    def test_get_submission(self, service: SubmissionContractService):
        """get_submission() reads one submission by uuid."""
        respx.get(f"{SUBMISSION_URL}/{SUBMISSION_UUID}").respond(
            200, json=submission_response("current")
        )

        submission = service.get_submission(SUBMISSION_UUID)

        assert isinstance(submission, Submission)
        assert str(submission.uuid) == SUBMISSION_UUID
        assert submission.state == "current"

    @respx.mock
    def test_list_submissions(self, service: SubmissionContractService):
        """list_submissions() returns every submission of a submission contract."""
        route = respx.get(f"{CONTRACT_URL}/submission3/data").respond(
            200,
            json=page(
                [submission_response("superseded"), submission_response("current")]
            ),
        )

        submissions = service.list_submissions("submission3")

        assert "limit" not in route.calls.last.request.url.params
        assert all(isinstance(s, Submission) for s in submissions)
        assert [s.state for s in submissions] == ["superseded", "current"]

    @respx.mock
    def test_list_submissions_empty(self, service: SubmissionContractService):
        """A submission contract without submissions gives an empty list."""
        respx.get(f"{CONTRACT_URL}/submission3/data").respond(200, json=page([]))

        assert service.list_submissions("submission3") == []


def uploaded_parts(request: httpx.Request) -> list[EmailMessage]:
    """Split a multipart request body into its parts.

    Args:
        request (httpx.Request): The recorded request.

    Returns:
        list[EmailMessage]: One message per multipart part.
    """
    header = b"Content-Type: " + request.headers["content-type"].encode()
    message = BytesParser(policy=default).parsebytes(
        header + b"\r\n\r\n" + request.content
    )
    return list(message.iter_parts())


class TestUploadSubmission:
    @pytest.mark.parametrize(
        "file",
        [b"PAR1 bundle bytes", io.BytesIO(b"PAR1 bundle bytes")],
        ids=["bytes", "binary_io"],
    )
    @respx.mock
    def test_posts_the_file_unchanged(self, service: SubmissionContractService, file):
        """_upload_submission() posts one file part carrying the given name and
        bytes."""
        route = respx.post(f"{CONTRACT_URL}/submission3/data").respond(
            201, json=submission_response()
        )

        service._upload_submission("submission3", file, "bundle.parquet")

        (part,) = uploaded_parts(route.calls.last.request)
        assert part.get_filename() == "bundle.parquet"
        assert part.get_payload(decode=True) == b"PAR1 bundle bytes"

    @respx.mock
    def test_returns_the_received_submission(self, service: SubmissionContractService):
        respx.post(f"{CONTRACT_URL}/submission3/data").respond(
            201, json=submission_response("received")
        )

        submission = service._upload_submission(
            "submission3", b"PAR1", "bundle.parquet"
        )

        assert isinstance(submission, Submission)
        assert submission.state == "received"

    @pytest.mark.parametrize(
        "status, error",
        [
            (404, ResourceNotFoundError),
            (403, PermissionDeniedError),
            (409, ConflictError),
        ],
    )
    @respx.mock
    def test_failed_upload_raises_mapped_error(
        self, service: SubmissionContractService, status: int, error: type
    ):
        """A rejected upload, e.g. an unsupported file extension, raises the
        mapped exception."""
        respx.post(f"{CONTRACT_URL}/submission3/data").respond(
            status, json={"detail": "nope"}
        )

        with pytest.raises(error):
            service._upload_submission("submission3", b"PAR1", "bundle.parquet")


class TestErrors:
    @pytest.mark.parametrize(
        "status, error",
        [(404, ResourceNotFoundError), (403, PermissionDeniedError)],
    )
    @respx.mock
    def test_get_raises_mapped_error(
        self, service: SubmissionContractService, status: int, error: type
    ):
        """A failed read of a submission contract raises the mapped exception."""
        respx.get(f"{CONTRACT_URL}/missing").respond(status, json={"detail": "nope"})

        with pytest.raises(error):
            service.get("missing")

    @pytest.mark.parametrize(
        "status, error",
        [(404, ResourceNotFoundError), (403, PermissionDeniedError)],
    )
    @respx.mock
    def test_get_submission_raises_mapped_error(
        self, service: SubmissionContractService, status: int, error: type
    ):
        """A failed read of a submission raises the mapped exception."""
        respx.get(f"{SUBMISSION_URL}/{SUBMISSION_UUID}").respond(
            status, json={"detail": "nope"}
        )

        with pytest.raises(error):
            service.get_submission(SUBMISSION_UUID)


def test_client_exposes_service(auth_client: CrossClient):
    """The client exposes a `SubmissionContractService` as `submissions`."""
    assert isinstance(auth_client.submissions, SubmissionContractService)
