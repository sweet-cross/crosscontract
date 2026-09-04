from unittest.mock import patch

import pandas as pd
import pytest

from crosscontract import CrossClient, CrossSubmitter, UnclaimedRowsError
from crosscontract.contracts import SchemaValidationError
from crosscontract.crossclient.services import CrossContractResolver
from crosscontract.submission import (
    SubmissionContract,
    SubmissionHandler,
    TargetValidationError,
)

from .conftest import bundle, resolver_for

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

    def test_resolver_reads_through_the_client_contracts(self, client):
        submitter = CrossSubmitter(client=client)
        assert isinstance(submitter._resolver, CrossContractResolver)
        assert submitter._resolver._service is client.contracts

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


class TestSubmit:
    def test_submit_is_an_honest_stub(self, client):
        submitter = CrossSubmitter(client=client)
        with pytest.raises(NotImplementedError):
            submitter.submit()


@pytest.fixture
def full_bundle() -> pd.DataFrame:
    """A bundle whose every row is claimed: one for `t_a`, one for `t_year`."""
    return bundle(("a", "CH", 2020, 1.0), ("c", "DE", 2030, 4.0))


def submitter_resolving(client: CrossClient, **contracts) -> CrossSubmitter:
    """Build a submitter whose resolver answers with the given contracts.

    The constructor takes no resolver by design, so the double is assigned
    afterwards.

    Args:
        client (CrossClient): The client the submitter is built on.
        **contracts (BaseContract | None): One entry per contract name, holding
            what `resolve` returns for it.

    Returns:
        CrossSubmitter: The submitter, wired to the resolver double.
    """
    submitter = CrossSubmitter(client=client)
    submitter._resolver = resolver_for(**contracts)
    return submitter


@pytest.fixture
def submitter(client, contract_a, contract_c) -> CrossSubmitter:
    """A submitter whose resolver hands back both target contracts."""
    return submitter_resolving(client, contract_a=contract_a, contract_c=contract_c)


class TestValidateSubmissionSequence:
    """The order of the three steps, which is the feature.

    Each failure asserts that the later steps were never reached, not merely
    that the right exception surfaced.
    """

    def test_returns_validated_frames_keyed_by_target_name(
        self, submitter, contract, full_bundle
    ):
        data = submitter.validate_submission(contract, full_bundle)
        assert set(data) == {"t_a", "t_year"}
        assert list(data["t_a"]["region"]) == ["CH"]
        assert data["t_year"]["period"].dtype == "Int64"

    def test_a_failing_bundle_stops_before_the_handler(self, submitter, contract):
        """Step 1 fails, so no handler is even built."""
        with patch("crosscontract.submission.submitter.SubmissionHandler") as handler:
            with pytest.raises(SchemaValidationError):
                submitter.validate_submission(
                    contract, bundle((None, "CH", 2020, 1.0))
                )
        handler.assert_not_called()

    def test_unclaimed_rows_stop_before_the_targets(self, submitter, contract):
        """Step 2 fails, carrying the rows, and step 3 is never attempted."""
        df = bundle(("a", "CH", 2020, 1.0), ("b", "DE", 2020, 2.0))
        with patch.object(SubmissionHandler, "validate_targets") as validate_targets:
            with pytest.raises(UnclaimedRowsError) as exc_info:
                submitter.validate_submission(contract, df)
        pd.testing.assert_frame_equal(exc_info.value.unclaimed_rows, df.iloc[[1]])
        validate_targets.assert_not_called()

    def test_failing_target_data_is_collected_per_target(
        self, client, contract, bad_contract_a, contract_c, full_bundle
    ):
        """Step 3 fails with one entry per failing target."""
        submitter = submitter_resolving(
            client, contract_a=bad_contract_a, contract_c=contract_c
        )
        with pytest.raises(TargetValidationError) as exc_info:
            submitter.validate_submission(contract, full_bundle)
        assert set(exc_info.value.errors) == {"t_a"}

    def test_an_unresolvable_target_contract_escapes_uncollected(
        self, client, contract, contract_a, full_bundle
    ):
        """A wiring error propagates rather than joining the collection."""
        submitter = submitter_resolving(client, contract_a=contract_a, contract_c=None)
        with pytest.raises(ValueError) as exc_info:
            submitter.validate_submission(contract, full_bundle)
        assert not isinstance(exc_info.value, TargetValidationError)
        assert "t_year" in str(exc_info.value)


class TestFlagForwarding:
    """The three flags reach both step 1 and step 3, unchanged."""

    @pytest.fixture
    def steps(self):
        """Spy on step 1 and step 3, leaving step 2 to run for real."""
        with (
            patch.object(SubmissionContract, "validate_data") as validate_data,
            patch.object(
                SubmissionHandler, "validate_targets", return_value={}
            ) as validate_targets,
        ):
            yield validate_data, validate_targets

    def test_defaults_reach_both_steps(self, submitter, contract, full_bundle, steps):
        validate_data, validate_targets = steps
        submitter.validate_submission(contract, full_bundle)
        expected = {
            "resolver": submitter._resolver,
            "check_existing_primary_key": True,
            "check_existing_foreign_key": True,
            "lazy": True,
        }
        assert validate_data.call_args.kwargs == expected
        assert validate_targets.call_args.kwargs == expected

    def test_explicit_flags_reach_both_steps(
        self, submitter, contract, full_bundle, steps
    ):
        validate_data, validate_targets = steps
        submitter.validate_submission(
            contract,
            full_bundle,
            check_existing_primary_key=False,
            check_existing_foreign_key=False,
            lazy=False,
        )
        expected = {
            "resolver": submitter._resolver,
            "check_existing_primary_key": False,
            "check_existing_foreign_key": False,
            "lazy": False,
        }
        assert validate_data.call_args.kwargs == expected
        assert validate_targets.call_args.kwargs == expected

    def test_the_bundle_reaches_step_one_unchanged(
        self, submitter, contract, full_bundle, steps
    ):
        validate_data, _ = steps
        submitter.validate_submission(contract, full_bundle)
        pd.testing.assert_frame_equal(validate_data.call_args.args[0], full_bundle)


class TestExtractionRunsOnTheRawBundle:
    def test_step_ones_coerced_frame_is_discarded(
        self, submitter, contract, full_bundle
    ):
        """Regression test for feeding step 1's output into the handler.

        Target filters match a column's string form, so a coerced value can
        change which target claims a row. Here `validate_data` hands back a
        frame whose routing column is mangled and whose `year` has widened to
        `float64` — if that frame reached the handler, no target would claim
        anything and step 2 would raise instead of returning.
        """
        coerced = full_bundle.assign(
            variable="zzz", year=full_bundle["year"].astype("float64")
        )
        with patch.object(SubmissionContract, "validate_data", return_value=coerced):
            data = submitter.validate_submission(contract, full_bundle)
        assert set(data) == {"t_a", "t_year"}
        assert list(data["t_a"]["region"]) == ["CH"]
