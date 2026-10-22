from pathlib import Path
from unittest.mock import create_autospec, patch

import pytest

from crosscontract import CrossClient, CrossSubmitter
from crosscontract.crossclient.services import (
    SubmissionContractResource,
    SubmissionContractService,
)
from crosscontract.exceptions import FileReadError
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
        from crosscontract.services.submitter import CrossSubmitter as FromSubmitter

        assert FromSubmitter is CrossSubmitter

    def test_listed_in_all(self):
        import crosscontract
        import crosscontract.services.submitter

        assert "CrossSubmitter" in crosscontract.__all__
        assert "CrossSubmitter" in crosscontract.services.submitter.__all__


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

    def test_defaults_are_forwarded(self, client, resource, get):
        df = bundle(("a", "CH", 2020, 1.0))
        CrossSubmitter(client=client).submit("submission3", df)

        arguments = bound_arguments(
            SubmissionContractResource.submit, resource.submit.call_args
        )
        assert arguments["filename"] is None
        assert arguments["validate"] is True

    def test_filename_and_validate_are_forwarded(self, client, resource, get):
        df = bundle(("a", "CH", 2020, 1.0))
        CrossSubmitter(client=client).submit(
            "submission3", df, filename="my_bundle", validate=False
        )

        arguments = bound_arguments(
            SubmissionContractResource.submit, resource.submit.call_args
        )
        assert arguments["filename"] == "my_bundle"
        assert arguments["validate"] is False


class TestSubmitFile:
    """The file is read by its extension, then handed to `submit`."""

    @pytest.fixture
    def resource(self):
        return create_autospec(SubmissionContractResource, instance=True)

    @pytest.fixture
    def get(self, resource):
        with patch.object(
            SubmissionContractService, "get", return_value=resource
        ) as get:
            yield get

    @pytest.fixture
    def submit(self):
        with patch.object(CrossSubmitter, "submit") as submit:
            yield submit

    @pytest.mark.parametrize(
        ("filename", "reader"),
        [
            ("bundle.csv", "read_csv_file"),
            ("bundle.CSV", "read_csv_file"),
            ("bundle.parquet", "read_parquet_file"),
            ("bundle.Parquet", "read_parquet_file"),
        ],
    )
    def test_reader_frame_is_submitted(self, client, get, submit, filename, reader):
        df = bundle(("a", "CH", 2020, 1.0))
        with patch(f"crosscontract.services.submitter.submitter.{reader}") as read:
            read.return_value = df
            result = CrossSubmitter(client=client).submit_file(
                "submission3", Path(filename), filename="stem", validate=False
            )

        read.assert_called_once_with(Path(filename))
        submit.assert_called_once_with(
            "submission3", df, filename="stem", validate=False
        )
        assert result is submit.return_value
        get.assert_not_called()

    @pytest.mark.parametrize("extension", [".xls", ".xlsx", ".xlsm", ".ods", ".XLSX"])
    def test_excel_is_read_with_the_fetched_contract(
        self, client, resource, get, submit, extension
    ):
        df = bundle(("a", "CH", 2020, 1.0))
        with patch(
            "crosscontract.services.submitter.submitter.read_excel_bundle",
            return_value=df,
        ) as read:
            CrossSubmitter(client=client).submit_file("submission3", f"b{extension}")

        get.assert_called_once_with("submission3")
        read.assert_called_once_with(resource.contract, Path(f"b{extension}"))
        submit.assert_called_once_with("submission3", df, filename=None, validate=True)

    @pytest.mark.parametrize("path", ["bundle.txt", "bundle", "bundle.csv.zip"])
    def test_unsupported_extension_raises_before_anything_is_fetched(
        self, client, get, submit, path
    ):
        with pytest.raises(ValueError, match=r"\.csv.*\.parquet.*\.xlsx"):
            CrossSubmitter(client=client).submit_file("submission3", path)

        get.assert_not_called()
        submit.assert_not_called()

    def test_read_failure_uploads_nothing(self, client, get, submit):
        with patch(
            "crosscontract.services.submitter.submitter.read_csv_file",
            side_effect=FileReadError("bad"),
        ):
            with pytest.raises(FileReadError):
                CrossSubmitter(client=client).submit_file("submission3", "bundle.csv")

        submit.assert_not_called()

    def test_csv_file_on_disk_is_submitted(self, client, get, submit, tmp_path):
        path = tmp_path / "bundle.csv"
        path.write_bytes(b"country,value\nNA,1.5")

        CrossSubmitter(client=client).submit_file("submission3", path)

        df = submit.call_args.args[1]
        assert df.loc[0, "country"] == "NA"
        assert df.loc[0, "value"] == 1.5


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
            check_existing_primary_key=False,
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
            check_existing_primary_key=True,
            check_existing_foreign_key=False,
            check_dimension_granularity=False,
            lazy=False,
        )
        resource.validate_submission.assert_called_once_with(
            df,
            check_existing_primary_key=True,
            check_existing_foreign_key=False,
            check_dimension_granularity=False,
            lazy=False,
        )
