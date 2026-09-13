import pandas as pd
import pytest

from crosscontract.contracts import BaseContract, CrossContract, SchemaValidationError
from crosscontract.contracts.contracts.resolvers import ContractResolver


class RecordingResolver:
    """Dict-backed `ContractResolver` that records every `get_data` call.

    Duck-typed on purpose: it satisfies the protocol structurally, without
    inheriting from it.
    """

    def __init__(
        self,
        data: dict[str, pd.DataFrame] | None = None,
        contracts: dict[str, BaseContract] | None = None,
    ):
        self._data = data or {}
        self._contracts = contracts or {}
        self.calls: list[tuple[str, tuple[str, ...]]] = []
        self.resolved: list[str] = []

    def resolve(self, name: str) -> BaseContract | None:
        self.resolved.append(name)
        return self._contracts.get(name)

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
        [
            "check_existing_primary_key",
            "check_existing_foreign_key",
            "check_dimension_granularity",
        ],
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


class TestPrimaryKeyWithinTheData:
    """The primary key is checked within the data whatever the flag says."""

    @pytest.fixture
    def contract(self):
        return _contract("simple", ID_VALUE_FIELDS, primary_key=["id"])

    @pytest.mark.parametrize(
        "ids",
        [[1, 1], pd.array([1, None], dtype="Int64")],
        ids=["duplicate", "null"],
    )
    @pytest.mark.parametrize("with_resolver", [False, True])
    def test_invalid_key_fails_without_the_existing_check(
        self, contract, ids, with_resolver
    ):
        resolver = RecordingResolver() if with_resolver else None
        df = pd.DataFrame({"id": ids, "value": [1.0, 2.0]})
        with pytest.raises(SchemaValidationError) as exc_info:
            contract.validate_data(df, resolver=resolver)
        assert any(
            "primary key" in str(error["check"]) for error in exc_info.value.to_list()
        )

    def test_contract_without_primary_key_accepts_duplicates(self):
        contract = _contract("simple", ID_VALUE_FIELDS)
        df = pd.DataFrame({"id": [1, 1], "value": [1.0, 1.0]})
        contract.validate_data(df)


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

    def test_reads_referenced_fields_from_referenced_contract(self, contract, resolver):
        """The lookup is `region.id`, never `region.region_code` or `emissions.*`."""
        df = pd.DataFrame({"id": [1, 2], "region_code": [10, 11], "value": [1.0, 2.0]})
        contract.validate_data(df, resolver=resolver, check_existing_foreign_key=True)
        assert resolver.calls == [("region", ("id",))]

    def test_unknown_reference_fails(self, contract, resolver):
        df = pd.DataFrame({"id": [1, 2], "region_code": [10, 99], "value": [1.0, 2.0]})
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
            foreign_keys=[{"fields": ["parent_id"], "reference": {"fields": ["id"]}}],
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

        Without the `df[columns]` reindex in `_get_existing_values` the valid
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


class TestDimensionGranularityDerivation:
    """Which references are recognised as hierarchical, and what is read.

    Unlike the key checks, this one needs both halves of the resolver protocol:
    `resolve` to learn that a reference is a hierarchical dimension, `get_data`
    to read its shape.
    """

    @staticmethod
    def _cross_contract(name: str, contract_type: str, **tableschema) -> CrossContract:
        return CrossContract.model_validate(
            {
                "name": name,
                "title": name,
                "description": name,
                "contract_type": contract_type,
                "tableschema": tableschema,
            }
        )

    @pytest.fixture
    def dimension(self) -> CrossContract:
        """A hierarchical dimension: the rigid `id` / `parent_id` template."""
        return self._cross_contract("dim_region", "Dimension")

    @pytest.fixture
    def flexible_dimension(self) -> CrossContract:
        """A flat dimension. It is a `BaseDimensionSchema` but not a
        `DimensionSchema`, and has no hierarchy to check."""
        return self._cross_contract(
            "dim_scenario",
            "FlexibleDimension",
            primaryKey=["name"],
            fields=[
                {"name": "name", "type": "string"},
                {"name": "label", "type": "string"},
                {"name": "description", "type": "string"},
            ],
        )

    @pytest.fixture
    def contract(self) -> CrossContract:
        """A ValueVariable referencing both kinds of dimension."""
        return self._cross_contract(
            "emissions",
            "ValueVariable",
            primaryKey=["region", "scenario", "year"],
            foreignKeys=[
                {
                    "fields": ["region"],
                    "reference": {"resource": "dim_region", "fields": ["id"]},
                },
                {
                    "fields": ["scenario"],
                    "reference": {"resource": "dim_scenario", "fields": ["name"]},
                },
            ],
            fields=[
                {"name": "region", "type": "string"},
                {"name": "scenario", "type": "string"},
                {"name": "year", "type": "integer"},
                {"name": "value", "type": "number"},
            ],
        )

    @pytest.fixture
    def resolver(self, dimension, flexible_dimension) -> RecordingResolver:
        """`ch_ag` and `ch_other` sit under `ch`; `ch` and `other` are roots."""
        return RecordingResolver(
            data={
                "dim_region": pd.DataFrame(
                    {
                        "id": ["ch", "other", "ch_ag", "ch_other"],
                        "parent_id": [None, None, "ch", "ch"],
                    }
                )
            },
            contracts={
                "dim_region": dimension,
                "dim_scenario": flexible_dimension,
            },
        )

    @staticmethod
    def _df(rows: list[tuple[str, str, int]]) -> pd.DataFrame:
        return pd.DataFrame(
            [{"region": r, "scenario": s, "year": y, "value": 1.0} for r, s, y in rows]
        )

    def test_flag_unset_consults_the_resolver_for_nothing(self, contract, resolver):
        """The check is opt-in, so a supplied resolver stays untouched."""
        contract.validate_data(self._df([("ch", "A", 2030), ("ch_ag", "A", 2030)]))
        contract.validate_data(
            self._df([("ch", "A", 2030), ("ch_ag", "A", 2030)]), resolver=resolver
        )
        assert resolver.resolved == []
        assert resolver.calls == []

    def test_hierarchical_dimension_is_resolved_and_read(self, contract, resolver):
        """The dimension's own `id` and `parent_id` are what is fetched — the
        column names come from the reference and from the rigid template."""
        contract.validate_data(
            self._df([("ch", "A", 2030)]),
            resolver=resolver,
            check_dimension_granularity=True,
        )
        assert resolver.calls == [("dim_region", ("id", "parent_id"))]

    def test_flexible_dimension_is_never_read(self, contract, resolver):
        """The regression that matters: `FlexibleDimensionSchema` is also a
        `BaseDimensionSchema`, so a loose isinstance test would derive a check
        for `dim_scenario` — which is flat and has no `parent_id` to read."""
        contract.validate_data(
            self._df([("ch", "A", 2030)]),
            resolver=resolver,
            check_dimension_granularity=True,
        )
        assert "dim_scenario" not in [name for name, _ in resolver.calls]

    def test_aggregate_beside_its_child_is_rejected(self, contract, resolver):
        """End to end: the frame reports `ch` and `ch_ag` for one scenario and
        year, so `ch` counts `ch_ag` twice."""
        df = self._df([("ch", "A", 2030), ("ch_ag", "A", 2030)])
        with pytest.raises(SchemaValidationError):
            contract.validate_data(
                df, resolver=resolver, check_dimension_granularity=True
            )

    def test_aggregate_and_child_in_different_groups_pass(self, contract, resolver):
        """The same two members under different scenarios are two groups, each
        summing correctly on its own."""
        df = self._df([("ch", "A", 2030), ("ch_ag", "B", 2030)])
        contract.validate_data(df, resolver=resolver, check_dimension_granularity=True)

    def test_root_members_reach_the_check_as_having_no_parent(self, contract, resolver):
        """A root's `parent_id` arrives from the frame as a null and must reach
        `HasNoDescendantInGroup` as `None`, the only null its `parent_map`
        accepts. Here the frame spells it `None` already, in an object column.
        Two roots in one group is the case that exercises it."""
        df = self._df([("ch", "A", 2030), ("other", "A", 2030)])
        contract.validate_data(df, resolver=resolver, check_dimension_granularity=True)

    def test_float_null_parents_are_normalised(
        self, contract, dimension, flexible_dimension
    ):
        """The same, for a frame that spells a missing parent as a float `NaN`.
        A dimension whose members are all roots comes back with a `parent_id`
        column typed `float64`, and a resolver reading a tabular source spells a
        blank cell that way too. `parent_map` takes `str | None` and rejects a
        float, so this is the shape the normalisation exists for."""
        resolver = RecordingResolver(
            data={
                "dim_region": pd.DataFrame(
                    {
                        "id": ["ch", "other"],
                        "parent_id": [float("nan"), float("nan")],
                    }
                )
            },
            contracts={
                "dim_region": dimension,
                "dim_scenario": flexible_dimension,
            },
        )
        df = self._df([("ch", "A", 2030), ("other", "A", 2030)])
        contract.validate_data(df, resolver=resolver, check_dimension_granularity=True)

    def test_non_value_variable_contract_derives_nothing(self, dimension):
        """A `General` contract may reference a dimension, but its group cannot
        be trusted: nothing forces its non-numeric fields into the primary key."""
        general = self._cross_contract(
            "notes",
            "General",
            primaryKey=["region"],
            foreignKeys=[
                {
                    "fields": ["region"],
                    "reference": {"resource": "dim_region", "fields": ["id"]},
                }
            ],
            fields=[
                {"name": "region", "type": "string"},
                {"name": "note", "type": "string"},
            ],
        )
        resolver = RecordingResolver(contracts={"dim_region": dimension})
        df = pd.DataFrame({"region": ["ch", "ch_ag"], "note": ["a", "b"]})
        general.validate_data(df, resolver=resolver, check_dimension_granularity=True)
        assert resolver.resolved == []

    def test_unresolvable_reference_raises(self, contract):
        """An unresolvable contract is a wiring error, not a data defect, so it
        is raised rather than skipped — naming both the column and the contract
        that could not be found."""
        resolver = RecordingResolver()
        df = self._df([("ch", "A", 2030)])
        with pytest.raises(ValueError, match="dim_region") as exc_info:
            contract.validate_data(
                df, resolver=resolver, check_dimension_granularity=True
            )
        assert "region" in str(exc_info.value)

    def test_composite_reference_is_skipped(self, dimension):
        """A `DimensionSchema` primary key is the single `id`, so a composite
        key referencing one is malformed. Reference validation owns that; here
        it is passed over rather than guessing which column carries members."""
        composite = self._cross_contract(
            "pairs",
            "ValueVariable",
            primaryKey=["region", "level"],
            foreignKeys=[
                {
                    "fields": ["region", "level"],
                    "reference": {"resource": "dim_region", "fields": ["id", "level"]},
                }
            ],
            fields=[
                {"name": "region", "type": "string"},
                {"name": "level", "type": "string"},
                {"name": "value", "type": "number"},
            ],
        )
        resolver = RecordingResolver(contracts={"dim_region": dimension})
        df = pd.DataFrame(
            {"region": ["ch", "ch_ag"], "level": ["0", "1"], "value": [1.0, 2.0]}
        )
        composite.validate_data(df, resolver=resolver, check_dimension_granularity=True)
        assert resolver.calls == []


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
