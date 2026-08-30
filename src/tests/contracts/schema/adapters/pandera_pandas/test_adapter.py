import pytest

from crosscontract.contracts.schema import DimensionSchema, TableSchema
from crosscontract.contracts.schema.adapters.pandera_pandas import (
    PanderaAdapter,
    convert_schema_to_pandera,
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
# add_internal_checks: what the schema requires of its own data
# ---------------------------------------------------------------------------


class TestAddInternalChecks:
    """Test the checks derived from the schema itself."""

    def test_schema_without_keys_gets_no_checks(self, adapter: PanderaAdapter):
        """Nothing to enforce beyond the columns."""
        schema = adapter.add_internal_checks(adapter.create_base_schema())
        assert not schema.checks

    def test_primary_key_adds_its_three_rules(self):
        """A primary key is non-null, unique, and absent from the existing keys,
        reported as three checks."""
        schema = TableSchema.model_validate(
            {"fields": [{"name": "id", "type": "string"}], "primaryKey": ["id"]}
        )
        adapter = PanderaAdapter(schema)
        result = adapter.add_internal_checks(adapter.create_base_schema())
        assert len(result.checks) == 3

    def test_self_referencing_foreign_key_is_checked(self):
        """A self-reference needs nothing from outside the data, so it runs."""
        schema = TableSchema.model_validate(
            {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "parent_id", "type": "string"},
                ],
                "foreignKeys": [
                    {"fields": ["parent_id"], "reference": {"fields": ["id"]}}
                ],
            }
        )
        adapter = PanderaAdapter(schema)
        result = adapter.add_internal_checks(adapter.create_base_schema())
        assert len(result.checks) == 1

    def test_external_foreign_key_is_not_checked(self):
        """A reference to another contract cannot be validated without its
        values, so no check is emitted here."""
        schema = TableSchema.model_validate(
            {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "region", "type": "string"},
                ],
                "foreignKeys": [
                    {
                        "fields": ["region"],
                        "reference": {"resource": "regions", "fields": ["id"]},
                    }
                ],
            }
        )
        adapter = PanderaAdapter(schema)
        result = adapter.add_internal_checks(adapter.create_base_schema())
        assert not result.checks

    def test_dimension_adds_its_hierarchy_rules(self):
        """A dimension carries its primary key, its self-reference and the four
        hierarchy rules."""
        adapter = PanderaAdapter(DimensionSchema.model_validate({}))
        result = adapter.add_internal_checks(adapter.create_base_schema())
        assert len(result.checks) == 3 + 1 + 4

    def test_the_base_schema_is_left_untouched(self, adapter: PanderaAdapter):
        """The checks are added to a copy, so the schema passed in is unchanged."""
        base = adapter.create_base_schema()
        adapter.add_internal_checks(base)
        assert not base.checks


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
