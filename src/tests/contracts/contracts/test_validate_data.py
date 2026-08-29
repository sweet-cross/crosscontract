import pandas as pd
import pytest

from crosscontract.contracts import BaseContract, SchemaValidationError
from crosscontract.contracts.contracts.resolvers import ContractResolver


class RecordingResolver:
    """Dict-backed `ContractResolver` that records every `get_data` call.

    Duck-typed on purpose: it satisfies the protocol structurally, without
    inheriting from it.
    """

    def __init__(self, data: dict[str, pd.DataFrame] | None = None):
        self._data = data or {}
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def resolve(self, name: str) -> BaseContract | None:
        return None

    def get_data(
        self, name: str, columns: list[str], *, unique: bool = True
    ) -> pd.DataFrame:
        self.calls.append((name, tuple(columns)))
        return self._data[name]


def _contract(name: str, fields: list[dict], primary_key=None, foreign_keys=None):
    """Build a BaseContract from field/key descriptions."""
    return BaseContract.model_validate(
        {
            "name": name,
            "tableschema": {
                "primaryKey": primary_key or [],
                "foreignKeys": foreign_keys or [],
                "fields": fields,
            },
        }
    )


ID_VALUE_FIELDS = [
    {"name": "id", "type": "integer"},
    {"name": "value", "type": "number"},
]


class TestResolverIsOptional:
    """`resolver=None` is a real mode; requesting a check without one is not."""

    @pytest.fixture
    def contract(self):
        return _contract("simple", ID_VALUE_FIELDS, primary_key=["id"])

    def test_validates_without_a_resolver(self, contract):
        df = pd.DataFrame({"id": [1, 2], "value": [1.0, 2.0]})
        contract.validate_data(df)

    def test_still_reports_schema_errors_without_a_resolver(self, contract):
        df = pd.DataFrame({"id": [1, 2], "value": ["a", "b"]})
        with pytest.raises(SchemaValidationError):
            contract.validate_data(df)

    def test_no_fetch_when_no_check_is_requested(self, contract):
        """A resolver may be supplied and must still not be read from."""
        resolver = RecordingResolver({"simple": pd.DataFrame({"id": [1]})})
        df = pd.DataFrame({"id": [1, 2], "value": [1.0, 2.0]})
        contract.validate_data(df, resolver=resolver)
        assert resolver.calls == []

    @pytest.mark.parametrize(
        "flag",
        ["check_existing_primary_key", "check_existing_foreign_key"],
    )
    def test_check_without_resolver_raises(self, contract, flag):
        df = pd.DataFrame({"id": [1], "value": [1.0]})
        with pytest.raises(ValueError, match="requires a resolver") as exc_info:
            contract.validate_data(df, **{flag: True})
        assert "simple" in str(exc_info.value)


class TestPrimaryKeyDerivation:
    """The primary key lookup targets the contract's own name."""

    @pytest.fixture
    def contract(self):
        return _contract("simple", ID_VALUE_FIELDS, primary_key=["id"])

    def test_looks_up_its_own_contract(self, contract):
        resolver = RecordingResolver({"simple": pd.DataFrame({"id": [10]})})
        df = pd.DataFrame({"id": [1, 2], "value": [1.0, 2.0]})
        contract.validate_data(df, resolver=resolver, check_existing_primary_key=True)
        assert resolver.calls == [("simple", ("id",))]

    def test_collision_with_stored_key_fails(self, contract):
        resolver = RecordingResolver({"simple": pd.DataFrame({"id": [1]})})
        df = pd.DataFrame({"id": [1, 2], "value": [1.0, 2.0]})
        with pytest.raises(SchemaValidationError):
            contract.validate_data(
                df, resolver=resolver, check_existing_primary_key=True
            )


class TestForeignKeyDerivation:
    """Referring fields and referenced fields must not be confused."""

    @pytest.fixture
    def contract(self):
        """`region_code` refers to `region.id` — the two names differ."""
        return _contract(
            "emissions",
            [
                {"name": "id", "type": "integer"},
                {"name": "region_code", "type": "integer"},
                {"name": "value", "type": "number"},
            ],
            primary_key=["id"],
            foreign_keys=[
                {
                    "fields": ["region_code"],
                    "reference": {"resource": "region", "fields": ["id"]},
                }
            ],
        )

    @pytest.fixture
    def resolver(self):
        return RecordingResolver({"region": pd.DataFrame({"id": [10, 11, 12]})})

    def test_reads_referenced_fields_from_referenced_contract(
        self, contract, resolver
    ):
        """The lookup is `region.id`, never `region.region_code` or `emissions.*`."""
        df = pd.DataFrame(
            {"id": [1, 2], "region_code": [10, 11], "value": [1.0, 2.0]}
        )
        contract.validate_data(df, resolver=resolver, check_existing_foreign_key=True)
        assert resolver.calls == [("region", ("id",))]

    def test_unknown_reference_fails(self, contract, resolver):
        df = pd.DataFrame(
            {"id": [1, 2], "region_code": [10, 99], "value": [1.0, 2.0]}
        )
        with pytest.raises(SchemaValidationError):
            contract.validate_data(
                df, resolver=resolver, check_existing_foreign_key=True
            )

    def test_self_reference_targets_own_contract(self):
        """A foreign key with no `resource` resolves to the contract itself."""
        contract = _contract(
            "hierarchy",
            [
                {"name": "id", "type": "integer"},
                {"name": "parent_id", "type": "integer"},
                {"name": "value", "type": "number"},
            ],
            primary_key=["id"],
            foreign_keys=[
                {"fields": ["parent_id"], "reference": {"fields": ["id"]}}
            ],
        )
        resolver = RecordingResolver({"hierarchy": pd.DataFrame({"id": [10]})})
        df = pd.DataFrame({"id": [1], "parent_id": [10], "value": [1.0]})
        contract.validate_data(df, resolver=resolver, check_existing_foreign_key=True)
        assert resolver.calls == [("hierarchy", ("id",))]


class TestCompositeForeignKeyColumnOrder:
    """Referring and referenced fields correspond by position, not by name."""

    @pytest.fixture
    def contract(self):
        return _contract(
            "pairs_fact",
            [
                {"name": "id", "type": "integer"},
                {"name": "a", "type": "integer"},
                {"name": "b", "type": "integer"},
                {"name": "value", "type": "number"},
            ],
            primary_key=["id"],
            foreign_keys=[
                {
                    "fields": ["a", "b"],
                    "reference": {"resource": "pair_dim", "fields": ["x", "y"]},
                }
            ],
        )

    def test_resolver_may_return_columns_in_any_order(self, contract):
        """The frame comes back as (y, x); the tuples must still be (x, y).

        Without the `df[columns]` reindex in `_get_reference_values` the valid
        set would be {(2, 1), (4, 3)} and the referring row (1, 2) would be
        rejected — silently, and only for composite keys.
        """
        resolver = RecordingResolver(
            {"pair_dim": pd.DataFrame({"y": [2, 4], "x": [1, 3]})}
        )
        df = pd.DataFrame({"id": [1], "a": [1], "b": [2], "value": [1.0]})
        contract.validate_data(df, resolver=resolver, check_existing_foreign_key=True)
        assert resolver.calls == [("pair_dim", ("x", "y"))]

    def test_transposed_pair_is_still_rejected(self, contract):
        """(2, 1) is not a valid pair even though both values appear."""
        resolver = RecordingResolver(
            {"pair_dim": pd.DataFrame({"y": [2, 4], "x": [1, 3]})}
        )
        df = pd.DataFrame({"id": [1], "a": [2], "b": [1], "value": [1.0]})
        with pytest.raises(SchemaValidationError):
            contract.validate_data(
                df, resolver=resolver, check_existing_foreign_key=True
            )


def test_stale_explicit_subclass_cannot_be_constructed():
    """`@abstractmethod` turns a missed protocol member into a build-time error.

    Without it an explicit subclass would inherit a `...` body, construct fine,
    and fail as an `AttributeError` deep inside validation.
    """

    class StaleResolver(ContractResolver):
        def resolve(self, name: str) -> BaseContract | None:
            return None

    with pytest.raises(TypeError, match="get_data"):
        StaleResolver()
