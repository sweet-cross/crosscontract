import pytest
from sqlalchemy import ARRAY, DateTime, Float, Integer, String

from crosscontract.contracts.schema import TableSchema
from crosscontract.contracts.schema.adapters import (
    SQLAlchemyPostgresAdapter,
    convert_schema_to_sqlalchemy,
)
from crosscontract.contracts.schema.fields import (
    DateTimeField,
    IntegerField,
    ListField,
    NumberField,
    StringField,
)


@pytest.fixture
def sample_schema():
    """Create a sample schema for testing."""
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
    ]
    return TableSchema.model_validate({"fields": fields})


@pytest.fixture
def adapter(sample_schema) -> SQLAlchemyPostgresAdapter:
    return SQLAlchemyPostgresAdapter(sample_schema)


# ---------------------------------------------------------------------------
# _create_column: type mapping
# ---------------------------------------------------------------------------


class TestCreateColumnTypeMapping:
    """Test that _create_column maps field types to the correct SQLAlchemy types."""

    def test_integer_field_returns_integer_type(
        self, adapter: SQLAlchemyPostgresAdapter
    ):
        field = IntegerField(name="age")
        column = adapter._create_column(field)
        assert isinstance(column.type, Integer)

    def test_number_field_returns_float_type(self, adapter: SQLAlchemyPostgresAdapter):
        field = NumberField(name="score")
        column = adapter._create_column(field)
        assert isinstance(column.type, Float)

    def test_string_field_returns_string_type(self, adapter: SQLAlchemyPostgresAdapter):
        field = StringField(name="label")
        column = adapter._create_column(field)
        assert isinstance(column.type, String)

    def test_datetime_field_returns_datetime_type(
        self, adapter: SQLAlchemyPostgresAdapter
    ):
        field = DateTimeField(name="created_at")
        column = adapter._create_column(field)
        assert isinstance(column.type, DateTime)

    def test_datetime_field_has_timezone_enabled(
        self, adapter: SQLAlchemyPostgresAdapter
    ):
        field = DateTimeField(name="created_at")
        column = adapter._create_column(field)
        assert column.type.timezone is True

    def test_list_of_strings_returns_array_type(
        self, adapter: SQLAlchemyPostgresAdapter
    ):
        field = ListField(name="tags", itemType="string")
        column = adapter._create_column(field)
        assert isinstance(column.type, ARRAY)

    def test_list_of_integers_returns_array_type(
        self, adapter: SQLAlchemyPostgresAdapter
    ):
        field = ListField(name="ids", itemType="integer")
        column = adapter._create_column(field)
        assert isinstance(column.type, ARRAY)

    def test_list_of_numbers_returns_array_type(
        self, adapter: SQLAlchemyPostgresAdapter
    ):
        field = ListField(name="scores", itemType="number")
        column = adapter._create_column(field)
        assert isinstance(column.type, ARRAY)

    def test_list_of_booleans_returns_array_type(
        self, adapter: SQLAlchemyPostgresAdapter
    ):
        field = ListField(name="flags", itemType="boolean")
        column = adapter._create_column(field)
        assert isinstance(column.type, ARRAY)


# ---------------------------------------------------------------------------
# _create_column: column name
# ---------------------------------------------------------------------------


class TestCreateColumnName:
    """Test that _create_column sets the column name correctly."""

    def test_column_name_matches_field_name(self, adapter: SQLAlchemyPostgresAdapter):
        field = StringField(name="my_field")
        column = adapter._create_column(field)
        assert column.name == "my_field"


# ---------------------------------------------------------------------------
# _create_column: nullable
# ---------------------------------------------------------------------------


class TestCreateColumnNullable:
    """Test that _create_column sets nullable based on field constraints."""

    def test_optional_field_is_nullable(self, adapter: SQLAlchemyPostgresAdapter):
        field = StringField(name="label", constraints={"required": False})
        column = adapter._create_column(field)
        assert column.nullable is True

    def test_required_field_is_not_nullable(self, adapter: SQLAlchemyPostgresAdapter):
        field = StringField(name="label", constraints={"required": True})
        column = adapter._create_column(field)
        assert column.nullable is False

    def test_default_constraints_is_nullable(self, adapter: SQLAlchemyPostgresAdapter):
        field = StringField(name="label")
        column = adapter._create_column(field)
        assert column.nullable is True


# ---------------------------------------------------------------------------
# convert: table-level behaviour
# ---------------------------------------------------------------------------


class TestConvert:
    """Test the full convert method on SQLAlchemyAdapter."""

    def test_table_name_is_set(self, adapter: SQLAlchemyPostgresAdapter):
        table = adapter.convert(table_name="my_table")
        assert table.name == "my_table"

    def test_primary_key_column_is_first(self, adapter: SQLAlchemyPostgresAdapter):
        table = adapter.convert(table_name="my_table")
        first_col = list(table.columns)[0]
        assert first_col.name == "_id"
        assert first_col.primary_key

    def test_column_count_includes_pk(self, adapter: SQLAlchemyPostgresAdapter):
        table = adapter.convert(table_name="my_table")
        # 3 schema fields + 1 _id primary key
        assert len(table.columns) == 4

    def test_schema_field_names_present(self, adapter: SQLAlchemyPostgresAdapter):
        table = adapter.convert(table_name="my_table")
        col_names = {col.name for col in table.columns}
        assert {"value", "year", "country"}.issubset(col_names)

    def test_creates_default_metadata_when_none(
        self, adapter: SQLAlchemyPostgresAdapter
    ):
        table = adapter.convert(table_name="my_table", metadata=None)
        assert table.metadata is not None

    def test_uses_provided_metadata(self, adapter: SQLAlchemyPostgresAdapter):
        from sqlalchemy import MetaData

        meta = MetaData()
        table = adapter.convert(table_name="my_table", metadata=meta)
        assert table.metadata is meta

    def test_schema_with_id_field_raises(self):
        fields = [{"name": "_id", "type": "integer"}]
        schema = TableSchema.model_validate({"fields": fields})
        with pytest.raises(ValueError, match="_id"):
            convert_schema_to_sqlalchemy(schema, table_name="my_table")

    def test_schema_field_names_present_classmethod(self, sample_schema):
        table = SQLAlchemyPostgresAdapter.convert_schema(
            sample_schema, table_name="my_table"
        )
        col_names = {col.name for col in table.columns}
        assert {"value", "year", "country"}.issubset(col_names)
