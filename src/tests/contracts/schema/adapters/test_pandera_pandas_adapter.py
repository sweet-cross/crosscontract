import pytest
from pandera import DateTime, Float64, Int64

from crosscontract.contracts.schema import TableSchema
from crosscontract.contracts.schema.adapters.pandera_adapter import (
    PanderaPandasAdapter,
    convert_schema_to_pandera,
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
def adapter(sample_schema) -> PanderaPandasAdapter:
    return PanderaPandasAdapter(sample_schema)


# ---------------------------------------------------------------------------
# _init_pandera_kwargs: shared column properties
# ---------------------------------------------------------------------------


class TestInitPanderaKwargs:
    """Test the shared kwargs initializer."""

    def test_required_field_is_not_nullable(self, adapter: PanderaPandasAdapter):
        field = StringField(name="label", constraints={"required": True})
        kwargs = adapter._init_pandera_kwargs(field, str)
        assert kwargs["required"] is True
        assert "nullable" not in kwargs

    def test_optional_field_is_nullable(self, adapter: PanderaPandasAdapter):
        field = StringField(name="label", constraints={"required": False})
        kwargs = adapter._init_pandera_kwargs(field, str)
        assert kwargs["required"] is False
        assert kwargs["nullable"] is True

    def test_name_and_dtype_are_set(self, adapter: PanderaPandasAdapter):
        field = IntegerField(name="age")
        kwargs = adapter._init_pandera_kwargs(field, Int64)
        assert kwargs["name"] == "age"
        assert kwargs["dtype"] is Int64

    def test_enum_constraint_adds_isin_check(self, adapter: PanderaPandasAdapter):
        field = StringField(
            name="color", constraints={"enum": ["red", "green", "blue"]}
        )
        kwargs = adapter._init_pandera_kwargs(field, str)
        assert len(kwargs["checks"]) == 1


# ---------------------------------------------------------------------------
# _convert_numeric_field
# ---------------------------------------------------------------------------


class TestConvertNumericField:
    """Test numeric field conversion."""

    def test_integer_field_uses_int64(self, adapter: PanderaPandasAdapter):
        field = IntegerField(name="age")
        col = adapter._convert_numeric_field(field)
        assert isinstance(col.dtype, Int64)

    def test_number_field_uses_float64(self, adapter: PanderaPandasAdapter):
        field = NumberField(name="score")
        col = adapter._convert_numeric_field(field)
        assert isinstance(col.dtype, Float64)

    def test_no_constraints_produces_no_checks(self, adapter: PanderaPandasAdapter):
        field = IntegerField(name="age")
        col = adapter._convert_numeric_field(field)
        assert col.checks == []

    def test_minimum_adds_ge_check(self, adapter: PanderaPandasAdapter):
        field = IntegerField(name="age", constraints={"minimum": 5})
        col = adapter._convert_numeric_field(field)
        assert len(col.checks) == 1

    def test_maximum_adds_le_check(self, adapter: PanderaPandasAdapter):
        field = IntegerField(name="age", constraints={"maximum": 10})
        col = adapter._convert_numeric_field(field)
        assert len(col.checks) == 1

    def test_both_constraints_add_two_checks(self, adapter: PanderaPandasAdapter):
        field = IntegerField(name="age", constraints={"minimum": 5, "maximum": 10})
        col = adapter._convert_numeric_field(field)
        assert len(col.checks) == 2

    def test_minimum_zero_is_not_skipped(self, adapter: PanderaPandasAdapter):
        field = IntegerField(name="age", constraints={"minimum": 0})
        col = adapter._convert_numeric_field(field)
        assert len(col.checks) == 1

    def test_unsupported_field_type_raises_error(self, adapter: PanderaPandasAdapter):
        with pytest.raises(ValueError):
            adapter._convert_numeric_field(StringField(name="label"))


# ---------------------------------------------------------------------------
# _convert_string_field
# ---------------------------------------------------------------------------


class TestConvertStringField:
    """Test string field conversion."""

    def test_no_constraints_produces_no_checks(self, adapter: PanderaPandasAdapter):
        field = StringField(name="label")
        col = adapter._convert_string_field(field)
        assert col.checks == []

    def test_pattern_sets_regex(self, adapter: PanderaPandasAdapter):
        field = StringField(name="code", constraints={"pattern": r"^[A-Z]+$"})
        col = adapter._convert_string_field(field)
        assert col.regex == r"^[A-Z]+$"

    def test_no_pattern_does_not_set_regex(self, adapter: PanderaPandasAdapter):
        field = StringField(name="label")
        col = adapter._convert_string_field(field)
        assert not col.regex

    def test_min_length_only(self, adapter: PanderaPandasAdapter):
        field = StringField(name="label", constraints={"minLength": 5})
        col = adapter._convert_string_field(field)
        assert len(col.checks) == 1
        assert col.checks[0]._check_kwargs["min_value"] == 5
        assert col.checks[0]._check_kwargs["max_value"] is None

    def test_max_length_only(self, adapter: PanderaPandasAdapter):
        field = StringField(name="label", constraints={"maxLength": 10})
        col = adapter._convert_string_field(field)
        assert len(col.checks) == 1
        assert col.checks[0]._check_kwargs["min_value"] is None
        assert col.checks[0]._check_kwargs["max_value"] == 10

    def test_both_length_constraints(self, adapter: PanderaPandasAdapter):
        field = StringField(name="label", constraints={"minLength": 5, "maxLength": 10})
        col = adapter._convert_string_field(field)
        assert len(col.checks) == 1
        assert col.checks[0]._check_kwargs["min_value"] == 5
        assert col.checks[0]._check_kwargs["max_value"] == 10


# ---------------------------------------------------------------------------
# _convert_list_field
# ---------------------------------------------------------------------------


class TestConvertListField:
    """Test list field conversion."""

    def test_no_constraints_produces_no_checks(self, adapter: PanderaPandasAdapter):
        field = ListField(name="tags", itemType="string")
        col = adapter._convert_list_field(field)
        assert col.checks == []

    def test_min_length_adds_check(self, adapter: PanderaPandasAdapter):
        field = ListField(name="tags", itemType="string", constraints={"minLength": 2})
        col = adapter._convert_list_field(field)
        assert len(col.checks) == 1

    def test_max_length_adds_check(self, adapter: PanderaPandasAdapter):
        field = ListField(name="tags", itemType="string", constraints={"maxLength": 10})
        col = adapter._convert_list_field(field)
        assert len(col.checks) == 1

    def test_both_length_constraints_add_two_checks(
        self, adapter: PanderaPandasAdapter
    ):
        field = ListField(
            name="tags",
            itemType="string",
            constraints={"minLength": 2, "maxLength": 10},
        )
        col = adapter._convert_list_field(field)
        assert len(col.checks) == 2


# ---------------------------------------------------------------------------
# _convert_datetime_field
# ---------------------------------------------------------------------------


class TestConvertDatetimeField:
    """Test datetime field conversion."""

    def test_dtype_is_datetime(self, adapter: PanderaPandasAdapter):
        field = DateTimeField(name="created_at")
        col = adapter._convert_datetime_field(field)
        assert isinstance(col.dtype, DateTime)

    def test_no_constraints_produces_no_checks(self, adapter: PanderaPandasAdapter):
        field = DateTimeField(name="created_at")
        col = adapter._convert_datetime_field(field)
        assert col.checks == []

    def test_minimum_adds_check(self, adapter: PanderaPandasAdapter):
        field = DateTimeField(
            name="created_at", constraints={"minimum": "2023-01-01 00:00"}
        )
        col = adapter._convert_datetime_field(field)
        assert len(col.checks) == 1

    def test_maximum_adds_check(self, adapter: PanderaPandasAdapter):
        field = DateTimeField(
            name="created_at", constraints={"maximum": "2023-12-31 00:00"}
        )
        col = adapter._convert_datetime_field(field)
        assert len(col.checks) == 1

    def test_both_constraints_add_two_checks(self, adapter: PanderaPandasAdapter):
        field = DateTimeField(
            name="created_at",
            constraints={
                "minimum": "2023-01-01 00:00",
                "maximum": "2023-12-31 00:00",
            },
        )
        col = adapter._convert_datetime_field(field)
        assert len(col.checks) == 2


# ---------------------------------------------------------------------------
# convert: full schema conversion
# ---------------------------------------------------------------------------


class TestConvert:
    """Test the full convert method."""

    def test_schema_name_is_set(self, adapter: PanderaPandasAdapter):
        schema = adapter.convert(name="MySchema")
        assert schema.name == "MySchema"

    def test_default_name(self, adapter: PanderaPandasAdapter):
        schema = adapter.convert()
        assert schema.name == "ConvertedSchema"

    def test_column_count_matches_schema(self, adapter: PanderaPandasAdapter):
        schema = adapter.convert()
        assert len(schema.columns) == 5

    def test_column_names_match_schema(self, adapter: PanderaPandasAdapter):
        schema = adapter.convert()
        assert set(schema.columns.keys()) == {
            "value",
            "year",
            "country",
            "created_at",
            "tags",
        }

    def test_strict_mode_enabled(self, sample_schema: TableSchema):
        schema = convert_schema_to_pandera(sample_schema)
        assert schema.strict is True

    def test_coerce_enabled(self, sample_schema: TableSchema):
        schema = PanderaPandasAdapter.convert_schema(sample_schema)
        assert schema.coerce is True
