import pytest

from crosscontract.contracts.schema import DimensionSchema, TableSchema
from crosscontract.contracts.schema.adapters.pandera_pandas import (
    PanderaAdapter,
    convert_schema_to_pandera,
)
from crosscontract.contracts.schema.validation.checks import (
    IsSubsetOf,
    IsValidCrossDimension,
    IsValidPrimaryKey,
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

    def test_primary_key_is_always_derived(self):
        """The key is checked within the frame whether or not stored values
        are supplied."""
        adapter = PanderaAdapter(self._schema(primaryKey=["id"]))
        (check,) = adapter._derive_checks()
        assert isinstance(check, IsValidPrimaryKey)
        assert check.columns == ["id"]
        assert check.existing == []

    def test_primary_key_carries_the_supplied_values(self):
        """Supplied keys become the set the frame must not collide with."""
        adapter = PanderaAdapter(self._schema(primaryKey=["id"]))
        (check,) = adapter._derive_checks(primary_key_values=[("a",)])
        assert check.existing == [("a",)]
        assert check.columns == ["id"]

    def test_self_referencing_foreign_key_is_always_derived(self):
        """A self-reference needs nothing from outside: the frame's own rows are
        the referenced values."""
        adapter = PanderaAdapter(
            self._schema(
                foreignKeys=[{"fields": ["parent_id"], "reference": {"fields": ["id"]}}]
            )
        )
        (check,) = adapter._derive_checks()
        assert isinstance(check, IsSubsetOf)
        assert check.columns == ["parent_id"]
        assert check.within == ["id"]
        assert check.allowed == []

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
        (check,) = adapter._derive_checks(
            foreign_key_values={("region",): [("de",)]}
        )
        assert isinstance(check, IsSubsetOf)
        assert check.within is None
        assert check.allowed == [("de",)]

    def test_values_for_an_unknown_key_are_ignored(self):
        """The schema's foreign keys drive the derivation, not the caller's
        dictionary, so a stray entry cannot invent a check."""
        adapter = PanderaAdapter(self._schema())
        assert adapter._derive_checks(foreign_key_values={("nope",): [("x",)]}) == []

    def test_dimension_derives_its_hierarchy_rules(self):
        """A dimension carries its key, its self-reference and the hierarchy."""
        adapter = PanderaAdapter(DimensionSchema.model_validate({}))
        checks = adapter._derive_checks()
        assert [type(c) for c in checks] == [
            IsValidPrimaryKey,
            IsSubsetOf,
            IsValidCrossDimension,
        ]


# ---------------------------------------------------------------------------
# convert: the two halves together
# ---------------------------------------------------------------------------


class TestConvert:
    """Test the full conversion and its two entry points."""

    def test_convert_carries_columns_and_checks(self):
        schema = TableSchema.model_validate(
            {"fields": [{"name": "id", "type": "string"}], "primaryKey": ["id"]}
        )
        result = PanderaAdapter(schema).convert()
        assert set(result.columns.keys()) == {"id"}
        assert len(result.checks) == 3

    def test_convert_schema_classmethod(self, sample_schema: TableSchema):
        """The classmethod converts without instantiating the adapter."""
        result = PanderaAdapter.convert_schema(sample_schema)
        assert len(result.columns) == 5

    def test_convert_schema_to_pandera_function(self, sample_schema: TableSchema):
        """The module-level function is the same conversion."""
        result = convert_schema_to_pandera(sample_schema)
        assert len(result.columns) == 5
        assert result.strict is True
        assert result.coerce is True
