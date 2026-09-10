import pytest

from crosscontract.contracts.schema import DimensionSchema, TableSchema
from crosscontract.contracts.schema.adapters.pandera_pandas import PanderaAdapter
from crosscontract.contracts.schema.validation.checks import (
    HasNoDescendantInGroup,
    IsSubsetOf,
    IsValidCrossDimension,
)

# These port the `TestConvert` cases from
# src/tests/contracts/schema/adapters/pandera/test_pandera_pandas_adapter.py and
# add the checks the conversion now derives from the schema itself. The two
# name cases do not port: `convert_schema_to_pandera` no longer takes a `name`.


@pytest.fixture
def sample_schema() -> TableSchema:
    """A schema with one field of every type and no keys."""
    fields = [
        {
            "name": "value",
            "type": "number",
            "constraints": {"required": True, "minimum": 0.0, "maximum": 100.0},
        },
        {
            "name": "year",
            "type": "integer",
            "constraints": {"required": True, "minimum": 2000, "maximum": 2025},
        },
        {
            "name": "country",
            "type": "string",
            "constraints": {"required": False, "maxLength": 6, "minLength": 2},
        },
        {
            "name": "created_at",
            "type": "datetime",
            "constraints": {"required": True},
        },
        {
            "name": "tags",
            "type": "list",
            "itemType": "string",
            "constraints": {"required": False, "minLength": 1, "maxLength": 5},
        },
    ]
    return TableSchema.model_validate({"fields": fields})


@pytest.fixture
def adapter(sample_schema: TableSchema) -> PanderaAdapter:
    return PanderaAdapter(sample_schema)


# ---------------------------------------------------------------------------
# create_base_schema: columns only
# ---------------------------------------------------------------------------


class TestCreateBaseSchema:
    """Test the columns half of the conversion."""

    def test_column_count_matches_schema(self, adapter: PanderaAdapter):
        assert len(adapter.create_base_schema().columns) == 5

    def test_column_names_match_schema(self, adapter: PanderaAdapter):
        assert set(adapter.create_base_schema().columns.keys()) == {
            "value",
            "year",
            "country",
            "created_at",
            "tags",
        }

    def test_strict_mode_enabled(self, adapter: PanderaAdapter):
        assert adapter.create_base_schema().strict is True

    def test_coerce_enabled(self, adapter: PanderaAdapter):
        assert adapter.create_base_schema().coerce is True

    def test_no_checks_are_attached(self, adapter: PanderaAdapter):
        """The base schema carries column-level constraints only; the checks the
        schema requires of its own data are added separately."""
        assert not adapter.create_base_schema().checks


# ---------------------------------------------------------------------------
# _derive_checks: what the schema requires of its own data
# ---------------------------------------------------------------------------
class TestDeriveChecks:
    """Test the checks derived from the schema, before any pandera conversion.

    Asserted on the check objects rather than through the converted schema,
    because a composite unpacks into several pandera checks and counting those
    says little about which rules were derived.
    """

    @staticmethod
    def _schema(**kwargs) -> TableSchema:
        fields = [
            {"name": "id", "type": "string"},
            {"name": "parent_id", "type": "string"},
            {"name": "region", "type": "string"},
        ]
        return TableSchema.model_validate({"fields": fields, **kwargs})

    def test_schema_without_keys_derives_nothing(self):
        """No constructs, no checks."""
        assert PanderaAdapter(self._schema())._derive_checks() == []

    def test_primary_key_carries_the_supplied_values(self):
        """Supplied keys become the set the frame must not collide with."""
        adapter = PanderaAdapter(self._schema(primaryKey=["id"]))
        (check,) = adapter._derive_checks(primary_key_values=[("a",)])
        assert check.existing == [("a",)]
        assert check.columns == ["id"]

    def test_self_reference_keeps_within_when_values_are_supplied(self):
        """The supplied values join the frame's own rows rather than replacing
        them — dropping `within` here would reject a child whose parent is in
        the frame."""
        adapter = PanderaAdapter(
            self._schema(
                foreignKeys=[{"fields": ["parent_id"], "reference": {"fields": ["id"]}}]
            )
        )
        (check,) = adapter._derive_checks(
            foreign_key_values={("parent_id",): [("stored",)]}
        )
        assert check.within == ["id"]
        assert check.allowed == [("stored",)]

    def test_external_foreign_key_without_values_is_not_derived(self):
        """Nothing to compare against, so the reference goes unchecked."""
        adapter = PanderaAdapter(
            self._schema(
                foreignKeys=[
                    {
                        "fields": ["region"],
                        "reference": {"resource": "regions", "fields": ["id"]},
                    }
                ]
            )
        )
        assert adapter._derive_checks() == []

    def test_external_foreign_key_with_values_is_derived(self):
        """Given the referenced values it becomes checkable, and takes no
        `within` — the frame's own rows are not the referenced table."""
        adapter = PanderaAdapter(
            self._schema(
                foreignKeys=[
                    {
                        "fields": ["region"],
                        "reference": {"resource": "regions", "fields": ["id"]},
                    }
                ]
            )
        )
        (check,) = adapter._derive_checks(foreign_key_values={("region",): [("de",)]})
        assert isinstance(check, IsSubsetOf)
        assert check.within is None
        assert check.allowed == [("de",)]

    def test_an_external_key_without_values_is_skipped(self):
        """Asking for foreign key checks does not conjure one for a reference
        whose values were not supplied. The self-reference alongside it is
        unaffected — it takes its valid set from the frame."""
        adapter = PanderaAdapter(
            self._schema(
                foreignKeys=[
                    {"fields": ["parent_id"], "reference": {"fields": ["id"]}},
                    {
                        "fields": ["region"],
                        "reference": {"resource": "regions", "fields": ["id"]},
                    },
                ]
            )
        )
        checks = adapter._derive_checks(foreign_key_values={})
        assert [check.columns for check in checks] == [["parent_id"]]

    def test_values_for_an_unknown_key_are_ignored(self):
        """The schema's foreign keys drive the derivation, not the caller's
        dictionary, so a stray entry cannot invent a check."""
        adapter = PanderaAdapter(self._schema())
        assert adapter._derive_checks(foreign_key_values={("nope",): [("x",)]}) == []

    def test_dimension_derives_its_hierarchy_rules(self):
        """A dimension declares a key and a self-reference as well, but with no
        values supplied only the hierarchy is derived — it is the one rule that
        needs nothing from outside the data."""
        adapter = PanderaAdapter(DimensionSchema.model_validate({}))
        checks = adapter._derive_checks()
        assert [type(c) for c in checks] == [IsValidCrossDimension]


# ---------------------------------------------------------------------------
# _derive_checks: the granularity check the caller's hierarchies ask for
# ---------------------------------------------------------------------------
PARENT_MAP = {"ch": None, "ch_ag": "ch"}


class TestDeriveGranularityChecks:
    """Test the checks derived from `dimension_hierarchies`.

    Unlike the key checks, these answer to no schema construct: a schema records
    that a column references a resource, not that the resource is hierarchical.
    The mapping the caller supplies is therefore what decides which columns get a
    check, and the schema supplies only the group.
    """

    @staticmethod
    def _schema(columns: list[str]) -> TableSchema:
        """A schema whose primary key is the given columns, plus a measure."""
        fields = [{"name": name, "type": "string"} for name in columns]
        fields.append({"name": "value", "type": "number"})
        return TableSchema.model_validate({"fields": fields, "primaryKey": columns})

    def test_none_derives_no_granularity_check(self):
        """The check is opt-in: without a hierarchy there is nothing to compare
        a member against, so none is derived."""
        adapter = PanderaAdapter(self._schema(["model", "scenario", "region"]))
        assert adapter._derive_checks(dimension_hierarchies=None) == []

    def test_supplied_hierarchy_derives_one_check(self):
        """A hierarchy for one column derives exactly one check, carrying that
        column, the parent map it was given, and the granularity label."""
        adapter = PanderaAdapter(self._schema(["model", "scenario", "region"]))
        (check,) = adapter._derive_checks(dimension_hierarchies={"region": PARENT_MAP})
        assert isinstance(check, HasNoDescendantInGroup)
        assert check.column == "region"
        assert check.parent_map == PARENT_MAP
        assert check.label == "dimension granularity"

    def test_group_is_the_primary_key_without_the_dimension_column(self):
        """The group is what makes two rows comparable: everything identifying a
        row except the member itself, in the order the key declares."""
        adapter = PanderaAdapter(self._schema(["model", "scenario", "region", "year"]))
        (check,) = adapter._derive_checks(dimension_hierarchies={"region": PARENT_MAP})
        assert check.group_columns == ["model", "scenario", "year"]

    def test_two_columns_into_the_same_dimension_get_a_check_each(self):
        """A contract may reference one dimension twice — `from` and `to` both
        naming regions. Each column is checked against its own group, and the
        other stays in that group, so a flow out of 'ch' and a flow into 'ch_ag'
        do not constrain each other."""
        adapter = PanderaAdapter(self._schema(["model", "origin", "destination"]))
        checks = adapter._derive_checks(
            dimension_hierarchies={"origin": PARENT_MAP, "destination": PARENT_MAP}
        )
        assert [(c.column, c.group_columns) for c in checks] == [
            ("origin", ["model", "destination"]),
            ("destination", ["model", "origin"]),
        ]

    def test_unknown_column_raises(self):
        """A column the schema does not declare is a wiring mistake, not a data
        defect. Deriving a check for it would fail later inside pandera with a
        `KeyError` against the frame, so it is refused here and named."""
        adapter = PanderaAdapter(self._schema(["model", "region"]))
        with pytest.raises(ValueError, match="nope"):
            adapter._derive_checks(dimension_hierarchies={"nope": PARENT_MAP})

    def test_convert_attaches_the_check_to_the_pandera_schema(self):
        """The argument survives the trip through `convert`: one rule with one
        remedy becomes one pandera check."""
        schema = self._schema(["model", "region"])
        result = PanderaAdapter(schema).convert(
            dimension_hierarchies={"region": PARENT_MAP}
        )
        assert len(result.checks) == 1

    def test_convert_schema_classmethod_passes_the_hierarchies_on(self):
        """The classmethod entry point threads the argument the same way."""
        schema = self._schema(["model", "region"])
        result = PanderaAdapter.convert_schema(
            schema, dimension_hierarchies={"region": PARENT_MAP}
        )
        assert len(result.checks) == 1


# ---------------------------------------------------------------------------
# convert: the two halves together
# ---------------------------------------------------------------------------


class TestConvert:
    """Test the full conversion and its two entry points."""

    def test_convert_carries_columns_and_checks(self):
        schema = TableSchema.model_validate(
            {"fields": [{"name": "id", "type": "string"}], "primaryKey": ["id"]}
        )
        result = PanderaAdapter(schema).convert(primary_key_values=[("id",)])
        assert set(result.columns.keys()) == {"id"}
        assert len(result.checks) == 3

    def test_convert_schema_classmethod(self, sample_schema: TableSchema):
        """The classmethod converts without instantiating the adapter."""
        result = PanderaAdapter.convert_schema(sample_schema)
        assert len(result.columns) == 5
