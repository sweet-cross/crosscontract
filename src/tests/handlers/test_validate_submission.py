from unittest.mock import Mock, patch

import pandas as pd
import pytest

from crosscontract.contracts.submission import SubmissionContract
from crosscontract.exceptions import (
    SchemaValidationError,
    TargetValidationError,
    UnclaimedRowsError,
)
from crosscontract.handlers import SubmissionHandler
from tests.conftest import bundle, resolver_for


@pytest.fixture
def full_bundle() -> pd.DataFrame:
    """A bundle whose every row is claimed: one for `t_a`, one for `t_year`."""
    return bundle(("a", "CH", 2020, 1.0), ("c", "DE", 2030, 4.0))


@pytest.fixture
def resolver(contract_a, contract_c) -> Mock:
    """A resolver handing back both target contracts."""
    return resolver_for(contract_a=contract_a, contract_c=contract_c)


class TestValidateSubmissionSequence:
    """The order of the three steps, which is the feature.

    Each failure asserts that the later steps were never reached, not merely
    that the right exception surfaced.
    """

    def test_returns_validated_frames_keyed_by_target_name(
        self, contract, full_bundle, resolver
    ):
        data = SubmissionHandler(contract, full_bundle).validate_submission(resolver)
        assert set(data) == {"t_a", "t_year"}
        assert list(data["t_a"]["region"]) == ["CH"]
        assert data["t_year"]["period"].dtype == "Int64"

    def test_resolver_is_required(self, contract, full_bundle):
        with pytest.raises(TypeError):
            SubmissionHandler(contract, full_bundle).validate_submission()

    def test_a_failing_bundle_stops_before_the_targets(self, contract, resolver):
        """Step 1 fails, so neither step 2 nor step 3 is attempted."""
        handler = SubmissionHandler(contract, bundle((None, "CH", 2020, 1.0)))
        with (
            patch.object(SubmissionHandler, "unclaimed_rows") as unclaimed_rows,
            patch.object(SubmissionHandler, "validate_targets") as validate_targets,
        ):
            with pytest.raises(SchemaValidationError):
                handler.validate_submission(resolver)
        unclaimed_rows.assert_not_called()
        validate_targets.assert_not_called()

    def test_unclaimed_rows_stop_before_the_targets(self, contract, resolver):
        """Step 2 fails, carrying the rows, and step 3 is never attempted."""
        df = bundle(("a", "CH", 2020, 1.0), ("b", "DE", 2020, 2.0))
        with patch.object(SubmissionHandler, "validate_targets") as validate_targets:
            with pytest.raises(UnclaimedRowsError) as exc_info:
                SubmissionHandler(contract, df).validate_submission(resolver)
        pd.testing.assert_frame_equal(exc_info.value.unclaimed_rows, df.iloc[[1]])
        validate_targets.assert_not_called()

    def test_failing_target_data_is_collected_per_target(
        self, contract, bad_contract_a, contract_c, full_bundle
    ):
        """Step 3 fails with one entry per failing target."""
        resolver = resolver_for(contract_a=bad_contract_a, contract_c=contract_c)
        with pytest.raises(TargetValidationError) as exc_info:
            SubmissionHandler(contract, full_bundle).validate_submission(resolver)
        assert set(exc_info.value.errors) == {"t_a"}

    def test_an_unresolvable_target_contract_is_not_collected(
        self, contract, contract_a, full_bundle
    ):
        """A wiring error in step 3 propagates as is rather than joining the
        collection of target failures."""
        resolver = resolver_for(contract_a=contract_a, contract_c=None)
        with pytest.raises(ValueError) as exc_info:
            SubmissionHandler(contract, full_bundle).validate_submission(resolver)
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

    def test_defaults_reach_both_steps(self, contract, full_bundle, resolver, steps):
        """Only the stored primary keys are left unchecked by default."""
        validate_data, validate_targets = steps
        SubmissionHandler(contract, full_bundle).validate_submission(resolver)
        expected = {
            "resolver": resolver,
            "check_existing_primary_key": False,
            "check_existing_foreign_key": True,
            "check_dimension_granularity": True,
            "lazy": True,
        }
        assert validate_data.call_args.kwargs == expected
        assert validate_targets.call_args.kwargs == expected

    def test_explicit_flags_reach_both_steps(
        self, contract, full_bundle, resolver, steps
    ):
        validate_data, validate_targets = steps
        SubmissionHandler(contract, full_bundle).validate_submission(
            resolver,
            check_existing_primary_key=True,
            check_existing_foreign_key=False,
            check_dimension_granularity=False,
            lazy=False,
        )
        expected = {
            "resolver": resolver,
            "check_existing_primary_key": True,
            "check_existing_foreign_key": False,
            "check_dimension_granularity": False,
            "lazy": False,
        }
        assert validate_data.call_args.kwargs == expected
        assert validate_targets.call_args.kwargs == expected

    def test_the_bundle_reaches_step_one_unchanged(
        self, contract, full_bundle, resolver, steps
    ):
        validate_data, _ = steps
        SubmissionHandler(contract, full_bundle).validate_submission(resolver)
        pd.testing.assert_frame_equal(validate_data.call_args.args[0], full_bundle)


class TestExtractionRunsOnTheRawBundle:
    def test_step_ones_coerced_frame_is_discarded(
        self, contract, full_bundle, resolver
    ):
        """Regression test for feeding step 1's output into extraction.

        Target filters match a column's string form, so a coerced value can
        change which target claims a row. Here `validate_data` hands back a
        frame whose routing column is mangled and whose `year` has widened to
        `float64` — if that frame were extracted from, no target would claim
        anything and step 2 would raise instead of returning.
        """
        coerced = full_bundle.assign(
            variable="zzz", year=full_bundle["year"].astype("float64")
        )
        with patch.object(SubmissionContract, "validate_data", return_value=coerced):
            data = SubmissionHandler(contract, full_bundle).validate_submission(
                resolver
            )
        assert set(data) == {"t_a", "t_year"}
        assert list(data["t_a"]["region"]) == ["CH"]
