from unittest.mock import Mock

import pandas as pd
import pytest

from crosscontract.contracts import (
    BaseContract,
    ContractResolver,
    SchemaValidationError,
)
from crosscontract.submission import (
    SubmissionContract,
    SubmissionHandler,
    TargetValidationError,
)

from .conftest import bundle, resolver_for, resolver_returning, target_contract


class TestValidateTarget:
    def test_returns_the_validated_frame(
        self, contract: SubmissionContract, contract_a: BaseContract
    ):
        """Test that the target's rows are extracted, transformed and returned."""
        handler = SubmissionHandler(
            contract=contract,
            bundle=bundle(("a", "CH", 2020, 1.0), ("b", "DE", 2020, 2.0)),
        )
        data = handler.validate_target("t_a", contract=contract_a)
        assert list(data.columns) == ["region", "year", "value"]
        assert list(data["region"]) == ["CH"]
        assert list(data["value"]) == [1.0]

    def test_coerces_to_the_contracts_types(
        self, contract: SubmissionContract, contract_c: BaseContract
    ):
        """Test that the returned frame is coerced, not merely accepted.

        `t_year`'s own transformation casts `period` to a string; `contract_c`
        declares it an integer, so the validated frame carries it back as one.
        """
        handler = SubmissionHandler(
            contract=contract, bundle=bundle(("c", "DE", 2030, 4.0))
        )
        transformed = handler.get_target_data("t_year")
        assert transformed["period"].dtype == "string"

        data = handler.validate_target("t_year", contract=contract_c)
        assert data["period"].dtype == "Int64"
        assert list(data["period"]) == [2030]

    def test_resolves_the_contract_when_only_a_resolver_is_given(
        self, contract: SubmissionContract, contract_a: BaseContract
    ):
        """Test that the target's contract is looked up by name."""
        resolver = resolver_returning(contract_a)
        handler = SubmissionHandler(
            contract=contract, bundle=bundle(("a", "CH", 2020, 1.0))
        )
        data = handler.validate_target("t_a", resolver=resolver)
        resolver.resolve.assert_called_once_with("contract_a")
        assert list(data["region"]) == ["CH"]

    def test_contract_takes_precedence_over_the_resolver(
        self, contract: SubmissionContract, contract_a: BaseContract
    ):
        """Test that an explicit contract wins and the resolver is never asked.

        The resolver would hand back a contract declaring `region` an integer,
        which the target's rows cannot satisfy — so a resolved contract would
        surface as a failure rather than as a passing test.
        """
        resolver = resolver_returning(
            target_contract(
                "contract_a",
                [
                    {"name": "region", "type": "integer"},
                    {"name": "year", "type": "integer"},
                    {"name": "value", "type": "number"},
                ],
            )
        )
        handler = SubmissionHandler(
            contract=contract, bundle=bundle(("a", "CH", 2020, 1.0))
        )
        data = handler.validate_target("t_a", contract=contract_a, resolver=resolver)
        resolver.resolve.assert_not_called()
        assert list(data["region"]) == ["CH"]

    def test_passes_its_arguments_through_to_validate_data(
        self, contract: SubmissionContract
    ):
        """Test that the resolver, the check flags and `lazy` arrive unchanged,
        alongside the target's transformed rows."""
        resolver = Mock(spec=ContractResolver)
        target_contract_mock = Mock(spec=BaseContract)
        target_contract_mock.name = "contract_a"
        handler = SubmissionHandler(
            contract=contract, bundle=bundle(("a", "CH", 2020, 1.0))
        )

        handler.validate_target(
            "t_a",
            contract=target_contract_mock,
            resolver=resolver,
            check_existing_primary_key=True,
            check_existing_foreign_key=True,
            lazy=False,
        )

        target_contract_mock.validate_data.assert_called_once()
        args, kwargs = target_contract_mock.validate_data.call_args
        pd.testing.assert_frame_equal(args[0], handler.get_target_data("t_a"))
        assert kwargs == {
            "resolver": resolver,
            "check_existing_primary_key": True,
            "check_existing_foreign_key": True,
            "lazy": False,
        }

    def test_target_claiming_no_rows_returns_an_empty_frame(
        self, contract: SubmissionContract, contract_a: BaseContract
    ):
        """Test that an empty target validates to an empty frame, not an error."""
        handler = SubmissionHandler(
            contract=contract, bundle=bundle(("b", "DE", 2020, 2.0))
        )
        data = handler.validate_target("t_a", contract=contract_a)
        assert data.empty
        assert list(data.columns) == ["region", "year", "value"]


class TestValidateTargetGuards:
    """The ways the contract can fail to arrive, kept distinguishable."""

    @pytest.fixture
    def handler(self, contract: SubmissionContract) -> SubmissionHandler:
        return SubmissionHandler(
            contract=contract, bundle=bundle(("a", "CH", 2020, 1.0))
        )

    def test_contract_not_matching_the_target_raises(
        self, handler: SubmissionHandler, contract_c: BaseContract
    ):
        """Test that another target's contract is refused, naming both.

        `t_a` names `contract_a`; `contract_c` would validate its rows to
        something plausible-looking rather than raising.
        """
        with pytest.raises(ValueError) as exc_info:
            handler.validate_target("t_a", contract=contract_c)
        message = str(exc_info.value)
        assert "contract_c" in message
        assert "contract_a" in message

    def test_unresolvable_contract_raises(self, handler: SubmissionHandler):
        """Test that a resolver finding nothing names the target and the contract."""
        resolver = resolver_returning(None)
        with pytest.raises(ValueError) as exc_info:
            handler.validate_target("t_a", resolver=resolver)
        message = str(exc_info.value)
        assert "t_a" in message
        assert "contract_a" in message

    def test_neither_contract_nor_resolver_raises(self, handler: SubmissionHandler):
        """Test that the message names both remedies."""
        with pytest.raises(ValueError) as exc_info:
            handler.validate_target("t_a")
        message = str(exc_info.value)
        assert "contract" in message
        assert "resolver" in message

    def test_unknown_target_still_raises_key_error(
        self, handler: SubmissionHandler, contract_a: BaseContract
    ):
        """Test that an unknown target stays a `KeyError`, not one of the guards'
        `ValueError`s, so a caller looping targets can tell the two apart."""
        with pytest.raises(KeyError, match="No target with name 'nope' found."):
            handler.validate_target("nope", contract=contract_a)

    def test_check_without_resolver_surfaces_the_contracts_own_message(
        self, handler: SubmissionHandler, contract_a: BaseContract
    ):
        """Test that the handler adds no second guard for a check flag set with a
        contract but no resolver — `validate_data`'s own message comes through."""
        with pytest.raises(ValueError, match="requires a resolver") as exc_info:
            handler.validate_target(
                "t_a", contract=contract_a, check_existing_primary_key=True
            )
        assert "contract_a" in str(exc_info.value)


class TestValidateTargets:
    """The loop over every target, collecting failures rather than stopping."""

    @pytest.fixture
    def handler(self, contract: SubmissionContract) -> SubmissionHandler:
        """Return a handler over a bundle holding one row per target."""
        return SubmissionHandler(
            contract=contract,
            bundle=bundle(("a", "CH", 2020, 1.0), ("c", "DE", 2030, 4.0)),
        )

    def test_requires_a_resolver(self, handler: SubmissionHandler):
        """Test that omitting the resolver fails at the call, not per target."""
        with pytest.raises(TypeError):
            handler.validate_targets()  # type: ignore[call-arg]

    def test_returns_validated_frames_keyed_by_target_name(
        self,
        handler: SubmissionHandler,
        contract_a: BaseContract,
        contract_c: BaseContract,
    ):
        """Test that every target is validated and keyed by its own name rather
        than by the contract it names, and that the frames are coerced."""
        resolver = resolver_for(contract_a=contract_a, contract_c=contract_c)
        data = handler.validate_targets(resolver)
        assert set(data) == {"t_a", "t_year"}
        assert list(data["t_a"]["region"]) == ["CH"]
        assert data["t_year"]["period"].dtype == "Int64"

    def test_delegates_to_validate_target_per_target(self, handler: SubmissionHandler):
        """Test that the loop hands each target to `validate_target` with its
        arguments unchanged, doing no resolution of its own."""
        resolver = Mock(spec=ContractResolver)
        handler.validate_target = Mock(return_value=pd.DataFrame())  # type: ignore[method-assign]

        handler.validate_targets(
            resolver,
            check_existing_primary_key=True,
            check_existing_foreign_key=True,
            lazy=False,
        )

        expected = {
            "resolver": resolver,
            "check_existing_primary_key": True,
            "check_existing_foreign_key": True,
            "lazy": False,
        }
        assert [call.args for call in handler.validate_target.call_args_list] == [
            ("t_a",),
            ("t_year",),
        ]
        assert [call.kwargs for call in handler.validate_target.call_args_list] == [
            expected,
            expected,
        ]
        resolver.resolve.assert_not_called()

    def test_every_target_is_attempted_before_raising(
        self,
        handler: SubmissionHandler,
        bad_contract_a: BaseContract,
        bad_contract_c: BaseContract,
    ):
        """Test that a failing first target does not hide a failing second one."""
        resolver = resolver_for(contract_a=bad_contract_a, contract_c=bad_contract_c)
        with pytest.raises(TargetValidationError) as exc_info:
            handler.validate_targets(resolver)
        assert set(exc_info.value.errors) == {"t_a", "t_year"}
        assert all(
            isinstance(error, SchemaValidationError)
            for error in exc_info.value.errors.values()
        )

    def test_passing_frames_are_discarded_when_a_target_fails(
        self,
        handler: SubmissionHandler,
        contract_a: BaseContract,
        bad_contract_c: BaseContract,
    ):
        """Test that a partly successful run returns nothing at all.

        `t_a` validates cleanly, but its frame is not handed back alongside the
        failure — validation is all-or-nothing by decision, not by accident.
        """
        resolver = resolver_for(contract_a=contract_a, contract_c=bad_contract_c)
        with pytest.raises(TargetValidationError) as exc_info:
            handler.validate_targets(resolver)
        assert set(exc_info.value.errors) == {"t_year"}

    def test_the_error_names_the_failing_targets(
        self,
        handler: SubmissionHandler,
        bad_contract_a: BaseContract,
        bad_contract_c: BaseContract,
    ):
        """Test that both the message and the flattened rows carry the targets."""
        resolver = resolver_for(contract_a=bad_contract_a, contract_c=bad_contract_c)
        with pytest.raises(TargetValidationError) as exc_info:
            handler.validate_targets(resolver)
        message = str(exc_info.value)
        assert "t_a" in message
        assert "t_year" in message
        assert {row["target"] for row in exc_info.value.to_list()} == {"t_a", "t_year"}

    def test_a_wiring_failure_escapes_uncollected(
        self, handler: SubmissionHandler, bad_contract_a: BaseContract
    ):
        """Test that an unresolvable contract raises rather than joining the
        collection, even though an earlier target already failed on its data."""
        resolver = resolver_for(contract_a=bad_contract_a, contract_c=None)
        with pytest.raises(ValueError) as exc_info:
            handler.validate_targets(resolver)
        assert not isinstance(exc_info.value, TargetValidationError)
        assert "t_year" in str(exc_info.value)

    def test_an_extra_column_is_a_collected_failure(
        self, handler: SubmissionHandler, contract_c: BaseContract
    ):
        """Test that a forgotten `drop_columns` is collected, not escaping.

        The contract omits `year`, so the transformed frame carries a column the
        schema does not know — caught by `strict=True` as a schema failure like
        any other.
        """
        resolver = resolver_for(
            contract_a=target_contract(
                "contract_a",
                [
                    {"name": "region", "type": "string"},
                    {"name": "value", "type": "number"},
                ],
            ),
            contract_c=contract_c,
        )
        with pytest.raises(TargetValidationError) as exc_info:
            handler.validate_targets(resolver)
        assert set(exc_info.value.errors) == {"t_a"}

    def test_non_lazy_still_yields_one_error_per_failing_target(
        self,
        handler: SubmissionHandler,
        bad_contract_a: BaseContract,
        bad_contract_c: BaseContract,
    ):
        """Test that `lazy=False` shortens each target's report without turning
        the loop itself fail-fast."""
        resolver = resolver_for(contract_a=bad_contract_a, contract_c=bad_contract_c)
        with pytest.raises(TargetValidationError) as exc_info:
            handler.validate_targets(resolver, lazy=False)
        assert set(exc_info.value.errors) == {"t_a", "t_year"}


class TestSelectiveTargets:
    """Which targets a run covers, and what it costs on the wire."""

    @pytest.fixture
    def handler(self, contract: SubmissionContract) -> SubmissionHandler:
        """Return a handler over a bundle holding one row per target."""
        return SubmissionHandler(
            contract=contract,
            bundle=bundle(("a", "CH", 2020, 1.0), ("c", "DE", 2030, 4.0)),
        )

    @pytest.fixture
    def resolver(self, contract_a: BaseContract, contract_c: BaseContract) -> Mock:
        """Return a resolver holding both target contracts."""
        return resolver_for(contract_a=contract_a, contract_c=contract_c)

    def test_none_validates_every_target_in_declaration_order(
        self, handler: SubmissionHandler, resolver: Mock
    ):
        """Test that the default covers the whole bundle, keyed in the order the
        extraction instructions declare."""
        data = handler.validate_targets(resolver)
        assert list(data) == ["t_a", "t_year"]

    def test_a_subset_leaves_the_other_contracts_unresolved(
        self, handler: SubmissionHandler, resolver: Mock
    ):
        """Test that a named subset validates only those targets and asks the
        resolver for nothing else — a subset run stays cheap on the wire."""
        data = handler.validate_targets(resolver, targets=["t_year"])
        assert list(data) == ["t_year"]
        assert [call.args[0] for call in resolver.resolve.call_args_list] == [
            "contract_c"
        ]

    def test_an_empty_list_validates_nothing(
        self, handler: SubmissionHandler, resolver: Mock
    ):
        """Test that `[]` means empty where `None` means all."""
        assert handler.validate_targets(resolver, targets=[]) == {}
        resolver.resolve.assert_not_called()

    def test_an_unknown_name_raises_key_error(
        self, handler: SubmissionHandler, resolver: Mock
    ):
        """Test that an unknown name surfaces the lookup's KeyError rather than
        being skipped silently."""
        with pytest.raises(KeyError, match="No target with name 'nope' found."):
            handler.validate_targets(resolver, targets=["t_a", "nope"])

    def test_a_repeated_name_collapses(
        self, handler: SubmissionHandler, resolver: Mock
    ):
        """Test that naming a target twice is harmless.

        Whether it was validated once or twice is deliberately not pinned — only
        that the result carries one entry for it.
        """
        data = handler.validate_targets(resolver, targets=["t_a", "t_a"])
        assert list(data) == ["t_a"]
