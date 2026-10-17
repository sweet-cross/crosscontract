import inspect
import io
from unittest.mock import Mock, patch

import pandas as pd
import pytest
from pydantic import ValidationError as PydanticValidationError

from crosscontract.contracts.schema import SchemaValidationError
from crosscontract.contracts.submission import SubmissionContract
from crosscontract.crossclient.services import CrossContractResolver
from crosscontract.crossclient.services.submission.schemas import Submission
from crosscontract.crossclient.services.submission.submission_resource import (
    SubmissionContractResource,
)
from crosscontract.crossclient.services.submission.submission_service import (
    SubmissionContractService,
)
from crosscontract.exceptions import TargetValidationError, UnclaimedRowsError
from crosscontract.handlers.submission import SubmissionHandler
from tests.conftest import bound_arguments, bundle

from .conftest import entry_response, submission_response


@pytest.fixture
def service() -> Mock:
    """A stand-in for the `SubmissionContractService` the resource delegates to."""
    return Mock()


@pytest.fixture
def resource(service: Mock, contract: SubmissionContract) -> SubmissionContractResource:
    """A resource built from the shared `SubmissionContract` fixture."""
    return SubmissionContractResource.from_response(service, entry_response(contract))


class TestFromResponse:
    def test_builds_resource(self, service: Mock, contract: SubmissionContract):
        """from_response populates every property and parses the contract."""
        resource = SubmissionContractResource.from_response(
            service, entry_response(contract, allow_submissions=False)
        )
        assert resource.name == "submission3"
        assert resource.project_name == "project1"
        assert resource.title == "Test Submission"
        assert resource.description == contract.description
        assert resource.tags == contract.tags
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
        response = entry_response(contract)
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
            ("title", "other"),
            ("description", "other"),
            ("tags", ["other"]),
            ("allow_submissions", False),
        ],
    )
    def test_property_is_read_only(
        self, resource: SubmissionContractResource, attribute: str, value: object
    ):
        """Assigning to a property raises instead of changing local state."""
        with pytest.raises(AttributeError):
            setattr(resource, attribute, value)


class TestServiceDelegation:
    @pytest.mark.parametrize("allow", [False, True])
    def test_set_allow_submissions_updates_flag(
        self, service: Mock, contract: SubmissionContract, allow: bool
    ):
        """The service is called with the name and the value, which is then kept."""
        resource = SubmissionContractResource.from_response(
            service, entry_response(contract, allow_submissions=not allow)
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

    def test_refresh_name_mismatch(
        self,
        service: Mock,
        contract: SubmissionContract,
        resource: SubmissionContractResource,
    ):
        """refresh() raises if the platform returns a different submission contract."""
        other = contract.model_copy(update={"name": "something_else"})
        service.get.return_value = SubmissionContractResource.from_response(
            service, entry_response(other)
        )

        with pytest.raises(ValueError, match="does not match resource name"):
            resource.refresh()

    def test_refresh_replaces_state(self, service: Mock, contract: SubmissionContract):
        """refresh() re-fetches by name and replaces contract, project and flag."""
        resource = SubmissionContractResource.from_response(
            service, entry_response(contract, allow_submissions=True)
        )
        updated_contract = contract.model_copy(update={"title": "New title"})
        service.get.return_value = SubmissionContractResource.from_response(
            service,
            entry_response(
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
        submissions = [Submission.model_validate(submission_response())]
        service.list_submissions.return_value = submissions

        assert resource.submissions() == submissions
        service.list_submissions.assert_called_once_with("submission3")


class TestValidateSubmission:
    """The resource hands its stored contract and a client resolver to a handler."""

    signature = inspect.signature(SubmissionHandler.validate_submission)

    @pytest.fixture
    def df(self) -> pd.DataFrame:
        return bundle(("a", "CH", 2020, 1.0))

    @pytest.fixture
    def validate(self):
        """Replace the handler's `validate_submission`, recording `self` too."""
        with patch.object(
            SubmissionHandler,
            "validate_submission",
            autospec=True,
            return_value={"t_a": pd.DataFrame()},
        ) as validate:
            yield validate

    @classmethod
    def arguments(cls, validate: Mock) -> dict:
        """Bind the recorded call to the handler method's signature, defaults
        included, so the assertions do not depend on positional or keyword use."""
        args, kwargs = validate.call_args
        bound = cls.signature.bind(*args, **kwargs)
        bound.apply_defaults()
        return bound.arguments

    def test_handler_holds_the_stored_contract_and_the_bundle(
        self, resource, df, validate
    ):
        resource.validate_submission(df)
        handler = self.arguments(validate)["self"]
        assert handler.contract == resource.contract
        pd.testing.assert_frame_equal(handler.bundle, df)

    def test_resolver_reads_through_the_client_contracts(
        self, resource, service, df, validate
    ):
        resource.validate_submission(df)
        resolver = self.arguments(validate)["resolver"]
        assert isinstance(resolver, CrossContractResolver)
        assert resolver._service is service._client.contracts

    def test_returns_the_handlers_result(self, resource, df, validate):
        assert resource.validate_submission(df) == validate.return_value

    def test_default_flags_are_true(self, resource, df, validate):
        resource.validate_submission(df)
        arguments = self.arguments(validate)
        assert arguments["check_existing_primary_key"] is True
        assert arguments["check_existing_foreign_key"] is True
        assert arguments["check_dimension_granularity"] is True
        assert arguments["lazy"] is True

    def test_explicit_flags_are_forwarded(self, resource, df, validate):
        resource.validate_submission(
            df,
            check_existing_primary_key=False,
            check_existing_foreign_key=False,
            check_dimension_granularity=False,
            lazy=False,
        )
        arguments = self.arguments(validate)
        assert arguments["check_existing_primary_key"] is False
        assert arguments["check_existing_foreign_key"] is False
        assert arguments["check_dimension_granularity"] is False
        assert arguments["lazy"] is False


class TestSubmit:
    """`submit` validates through the resource, then uploads the delivered bundle."""

    @pytest.fixture
    def df(self) -> pd.DataFrame:
        return bundle(("a", "CH", 2020, 1.0))

    @pytest.fixture
    def validate(self, df):
        """Replace validation with one that passes, returning a coerced frame
        that differs from the bundle."""
        coerced = {"t_a": df.assign(year=df["year"].astype("float64"))}
        with patch.object(
            SubmissionContractResource, "validate_submission", return_value=coerced
        ) as validate:
            yield validate

    @staticmethod
    def uploaded(service: Mock) -> dict:
        return bound_arguments(
            SubmissionContractService._upload_submission,
            service._upload_submission.call_args,
        )

    def test_validates_before_uploading(self, resource, service, df, validate):
        order = []
        validate.side_effect = lambda *args, **kwargs: order.append("validate")
        service._upload_submission.side_effect = lambda *args, **kwargs: order.append(
            "upload"
        )

        resource.submit(df)

        assert order == ["validate", "upload"]

    def test_uploads_the_delivered_bundle_as_parquet(
        self, resource, service, df, validate
    ):
        """The frame as handed in is uploaded, dtypes intact, never the coerced
        one validation returns."""
        resource.submit(df)

        uploaded = self.uploaded(service)
        assert uploaded["name"] == resource.name
        file = uploaded["file"]
        content = file if isinstance(file, bytes) else file.read()
        pd.testing.assert_frame_equal(pd.read_parquet(io.BytesIO(content)), df)

    def test_returns_the_submission(self, resource, service, df, validate):
        assert resource.submit(df) is service._upload_submission.return_value

    @pytest.mark.parametrize(
        "error",
        [
            SchemaValidationError("bundle failed"),
            UnclaimedRowsError(pd.DataFrame({"variable": ["b"]})),
            TargetValidationError({}),
            ValueError("unresolvable target contract"),
        ],
        ids=["bundle", "unclaimed_rows", "targets", "references"],
    )
    def test_no_upload_when_validation_fails(
        self, resource, service, df, validate, error
    ):
        validate.side_effect = error

        with pytest.raises(type(error)):
            resource.submit(df)

        service._upload_submission.assert_not_called()

    def test_validation_runs_with_every_check_on(self, resource, df, validate):
        """`submit` passes only the bundle, so `validate_submission`'s defaults
        apply."""
        resource.submit(df)

        arguments = bound_arguments(
            SubmissionContractResource.validate_submission, validate.call_args
        )
        assert arguments["df"] is df
        assert arguments["check_existing_primary_key"] is True
        assert arguments["check_existing_foreign_key"] is True
        assert arguments["check_dimension_granularity"] is True
        assert arguments["lazy"] is True

    def test_validate_false_skips_validation_and_uploads(
        self, resource, service, df, validate
    ):
        resource.submit(df, validate=False)

        validate.assert_not_called()
        service._upload_submission.assert_called_once()

    @pytest.mark.parametrize(
        "filename, expected",
        [(None, "submission3.parquet"), ("my_bundle", "my_bundle.parquet")],
        ids=["default", "given_stem"],
    )
    def test_filename_is_the_stem_plus_parquet(
        self, resource, service, df, validate, filename, expected
    ):
        resource.submit(df, filename=filename)

        assert self.uploaded(service)["filename"] == expected
