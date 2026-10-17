from unittest.mock import create_autospec, patch

import pytest

from crosscontract import CrossClient, CrossSubmitter
from crosscontract.crossclient.services import (
    SubmissionContractResource,
    SubmissionContractService,
)
from tests.conftest import bound_arguments, bundle

USERNAME = "testuser"
PASSWORD = "secretpassword"


@pytest.fixture
def client() -> CrossClient:
    """A client whose construction does not reach the platform."""
    with patch("crosscontract.crossclient.crossclient.CrossClient.authenticate"):
        return CrossClient(USERNAME, PASSWORD)


class TestConstruction:
    def test_credentials_build_a_client(self):
        with patch("crosscontract.crossclient.crossclient.CrossClient.authenticate"):
            submitter = CrossSubmitter(username=USERNAME, password=PASSWORD)
        assert isinstance(submitter._client, CrossClient)

    def test_given_client_is_used_as_is(self, client):
        submitter = CrossSubmitter(client=client)
        assert submitter._client is client

    def test_client_wins_over_credentials(self, client):
        """No second client is built when one is handed in."""
        submitter = CrossSubmitter(username="other", password="other", client=client)
        assert submitter._client is client

    @pytest.mark.parametrize(
        "kwargs",
        [{}, {"username": USERNAME}, {"password": PASSWORD}],
        ids=["nothing", "username_only", "password_only"],
    )
    def test_incomplete_credentials_raise(self, kwargs):
        with pytest.raises(ValueError):
            CrossSubmitter(**kwargs)

    def test_resolver_is_not_a_constructor_parameter(self, client):
        with pytest.raises(TypeError):
            CrossSubmitter(client=client, resolver=object())


class TestPublicSurface:
    def test_exported_from_both_paths(self):
        """The module-level import already covers the top-level path."""
        from crosscontract.submission import CrossSubmitter as FromSubmission

        assert FromSubmission is CrossSubmitter

    def test_listed_in_all(self):
        import crosscontract

        assert "CrossSubmitter" in crosscontract.__all__
        assert "CrossSubmitter" in crosscontract.submission.__all__

    def test_reexports_handler_and_readers(self):
        import crosscontract.handlers.submission as service
        import crosscontract.submission as submission

        assert submission.SubmissionHandler is service.SubmissionHandler
        assert submission.read_excel_bundle is service.read_excel_bundle
        assert submission.read_excel_bundle_bytes is service.read_excel_bundle_bytes
        assert "SubmissionHandler" in submission.__all__
        assert "read_excel_bundle" in submission.__all__
        assert "read_excel_bundle_bytes" in submission.__all__


class TestSubmit:
    """The submitter fetches the submission contract by name and passes through."""

    @pytest.fixture
    def resource(self):
        return create_autospec(SubmissionContractResource, instance=True)

    @pytest.fixture
    def get(self, resource):
        with patch.object(
            SubmissionContractService, "get", return_value=resource
        ) as get:
            yield get

    def test_fetches_by_name_and_returns_the_submission(self, client, resource, get):
        df = bundle(("a", "CH", 2020, 1.0))

        result = CrossSubmitter(client=client).submit("submission3", df)

        get.assert_called_once_with("submission3")
        arguments = bound_arguments(
            SubmissionContractResource.submit, resource.submit.call_args
        )
        assert arguments["df"] is df
        assert result is resource.submit.return_value

    def test_default_flags_are_forwarded(self, client, resource, get):
        df = bundle(("a", "CH", 2020, 1.0))
        CrossSubmitter(client=client).submit("submission3", df)

        arguments = bound_arguments(
            SubmissionContractResource.submit, resource.submit.call_args
        )
        assert arguments["check_existing_primary_key"] is True
        assert arguments["check_existing_foreign_key"] is True
        assert arguments["check_dimension_granularity"] is True
        assert arguments["lazy"] is True

    def test_explicit_flags_are_forwarded(self, client, resource, get):
        CrossSubmitter(client=client).submit(
            "submission3",
            bundle(("a", "CH", 2020, 1.0)),
            check_existing_primary_key=False,
            check_existing_foreign_key=False,
            check_dimension_granularity=False,
            lazy=False,
        )

        arguments = bound_arguments(
            SubmissionContractResource.submit, resource.submit.call_args
        )
        assert arguments["check_existing_primary_key"] is False
        assert arguments["check_existing_foreign_key"] is False
        assert arguments["check_dimension_granularity"] is False
        assert arguments["lazy"] is False


class TestValidateSubmission:
    """The submitter fetches the submission contract by name and passes through."""

    @pytest.fixture
    def resource(self):
        return create_autospec(SubmissionContractResource, instance=True)

    @pytest.fixture
    def get(self, resource):
        with patch.object(
            SubmissionContractService, "get", return_value=resource
        ) as get:
            yield get

    def test_fetches_by_name_and_delegates_with_defaults(self, client, resource, get):
        df = bundle(("a", "CH", 2020, 1.0))
        result = CrossSubmitter(client=client).validate_submission("submission3", df)
        get.assert_called_once_with("submission3")
        resource.validate_submission.assert_called_once_with(
            df,
            check_existing_primary_key=True,
            check_existing_foreign_key=True,
            check_dimension_granularity=True,
            lazy=True,
        )
        assert result is resource.validate_submission.return_value

    def test_explicit_flags_are_forwarded(self, client, resource, get):
        df = bundle(("a", "CH", 2020, 1.0))
        CrossSubmitter(client=client).validate_submission(
            "submission3",
            df,
            check_existing_primary_key=False,
            check_existing_foreign_key=False,
            check_dimension_granularity=False,
            lazy=False,
        )
        resource.validate_submission.assert_called_once_with(
            df,
            check_existing_primary_key=False,
            check_existing_foreign_key=False,
            check_dimension_granularity=False,
            lazy=False,
        )
