from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from crosscontract.contracts.schema import TableSchema
from crosscontract.contracts.schema.adapters.pydantic_adapter import (
    PydanticAdapter,
    convert_schema_to_pydantic,
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
    """Create a sample DataContract for testing."""
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
def adapter(sample_schema) -> PydanticAdapter:
    return PydanticAdapter(sample_schema)


class TestNumericFieldConversion:
    """Test class for the numeric field conversion in PydanticAdapter."""

    # --- Type mapping ---

    def test_integer_field_returns_int_type(self, adapter: PydanticAdapter):
        field = IntegerField(name="age", constraints={"required": True})
        python_type, _ = adapter._convert_numeric_field(field)
        assert python_type is int

    def test_number_field_returns_float_type(self, adapter: PydanticAdapter):
        field = NumberField(name="score", constraints={"required": True})
        python_type, _ = adapter._convert_numeric_field(field)
        assert python_type is float

    # --- Required / optional ---

    def test_required_field_has_no_default(self, adapter: PydanticAdapter):
        field = IntegerField(name="year", constraints={"required": True})
        python_type, field_info = adapter._convert_numeric_field(field)
        assert python_type is int
        assert field_info.is_required()

    def test_optional_field_defaults_to_none(self, adapter: PydanticAdapter):
        field = IntegerField(name="year", constraints={"required": False})
        python_type, field_info = adapter._convert_numeric_field(field)
        # optional fields become Union[int, None]
        assert field_info.default is None
        assert not field_info.is_required()

    # --- Minimum / maximum constraints ---

    def test_minimum_constraint_mapped_to_ge(self, adapter: PydanticAdapter):
        field = IntegerField(
            name="year", constraints={"required": True, "minimum": 2000}
        )
        _, field_info = adapter._convert_numeric_field(field)
        assert field_info.metadata is not None
        ge_values = [m.ge for m in field_info.metadata if hasattr(m, "ge")]
        assert 2000 in ge_values

    def test_maximum_constraint_mapped_to_le(self, adapter: PydanticAdapter):
        field = IntegerField(
            name="year", constraints={"required": True, "maximum": 2025}
        )
        _, field_info = adapter._convert_numeric_field(field)
        le_values = [m.le for m in field_info.metadata if hasattr(m, "le")]
        assert 2025 in le_values

    def test_both_min_and_max_constraints(self, adapter: PydanticAdapter):
        field = NumberField(
            name="value",
            constraints={"required": True, "minimum": 0.0, "maximum": 100.0},
        )
        _, field_info = adapter._convert_numeric_field(field)
        ge_values = [m.ge for m in field_info.metadata if hasattr(m, "ge")]
        le_values = [m.le for m in field_info.metadata if hasattr(m, "le")]
        assert 0.0 in ge_values
        assert 100.0 in le_values

    def test_no_constraints_omits_ge_le(self, adapter: PydanticAdapter):
        field = IntegerField(name="count", constraints={"required": True})
        _, field_info = adapter._convert_numeric_field(field)
        ge_values = [m for m in field_info.metadata if hasattr(m, "ge")]
        le_values = [m for m in field_info.metadata if hasattr(m, "le")]
        assert ge_values == []
        assert le_values == []

    # --- Metadata (title, description, json_schema_extra) ---

    def test_field_name_stored_in_json_schema_extra(self, adapter: PydanticAdapter):
        field = IntegerField(name="year", constraints={"required": True})
        _, field_info = adapter._convert_numeric_field(field)
        assert field_info.json_schema_extra == {"name": "year"}

    def test_title_is_propagated(self, adapter: PydanticAdapter):
        field = IntegerField(
            name="year", title="The Year", constraints={"required": True}
        )
        _, field_info = adapter._convert_numeric_field(field)
        assert field_info.title == "The Year"

    def test_description_is_propagated(self, adapter: PydanticAdapter):
        field = NumberField(
            name="score", description="A numeric score", constraints={"required": True}
        )
        _, field_info = adapter._convert_numeric_field(field)
        assert field_info.description == "A numeric score"

    # --- Enum constraint ---

    def test_enum_constraint_creates_validator(self, adapter: PydanticAdapter):
        field = IntegerField(
            name="status", constraints={"required": True, "enum": [1, 2, 3]}
        )
        adapter._convert_numeric_field(field)
        assert "validate_enum_status" in adapter._validators

    def test_no_enum_constraint_skips_validator(self, adapter: PydanticAdapter):
        field = IntegerField(name="year", constraints={"required": True})
        adapter._convert_numeric_field(field)
        assert "validate_enum_year" not in adapter._validators

    def test_raises_value_error_for_unsupported_field_types(
        self, adapter: PydanticAdapter
    ):
        field = StringField(name="name", constraints={"required": True})
        with pytest.raises(ValueError):
            adapter._convert_numeric_field(field)


class TestEnumValidator:
    def test_enum_validator_allows_valid_values(self, adapter: PydanticAdapter):
        enum_values = [1, 2, 3]
        validator = adapter._make_enum_validator(enum_values)
        for value in enum_values:
            assert validator(value) == value

    def test_enum_validator_rejects_invalid_values(self, adapter: PydanticAdapter):
        enum_values = [1, 2, 3]
        validator = adapter._make_enum_validator(enum_values)
        with pytest.raises(ValueError):
            validator(4)


class TestStringFieldConversion:
    """Test class for the string field conversion in PydanticAdapter."""

    @pytest.fixture
    def adapter(self, sample_schema):
        return PydanticAdapter(sample_schema)

    # --- Type mapping ---

    def test_returns_str_type(self, adapter: PydanticAdapter):
        field = StringField(name="country", constraints={"required": True})
        python_type, _ = adapter._convert_string_field(field)
        assert python_type is str

    # --- Required / optional ---

    def test_required_field_has_no_default(self, adapter: PydanticAdapter):
        field = StringField(name="country", constraints={"required": True})
        _, field_info = adapter._convert_string_field(field)
        assert field_info.is_required()

    def test_optional_field_defaults_to_none(self, adapter: PydanticAdapter):
        field = StringField(name="country", constraints={"required": False})
        _, field_info = adapter._convert_string_field(field)
        assert field_info.default is None
        assert not field_info.is_required()

    # --- String length constraints ---

    def test_min_length_mapped(self, adapter: PydanticAdapter):
        field = StringField(name="code", constraints={"required": True, "minLength": 2})
        _, field_info = adapter._convert_string_field(field)
        min_lengths = [
            m.min_length for m in field_info.metadata if hasattr(m, "min_length")
        ]
        assert 2 in min_lengths

    def test_max_length_mapped(self, adapter: PydanticAdapter):
        field = StringField(name="code", constraints={"required": True, "maxLength": 6})
        _, field_info = adapter._convert_string_field(field)
        max_lengths = [
            m.max_length for m in field_info.metadata if hasattr(m, "max_length")
        ]
        assert 6 in max_lengths

    def test_both_min_and_max_length(self, adapter: PydanticAdapter):
        field = StringField(
            name="code",
            constraints={"required": True, "minLength": 2, "maxLength": 6},
        )
        _, field_info = adapter._convert_string_field(field)
        min_lengths = [
            m.min_length for m in field_info.metadata if hasattr(m, "min_length")
        ]
        max_lengths = [
            m.max_length for m in field_info.metadata if hasattr(m, "max_length")
        ]
        assert 2 in min_lengths
        assert 6 in max_lengths

    def test_no_length_constraints_omits_min_max(self, adapter: PydanticAdapter):
        field = StringField(name="note", constraints={"required": True})
        _, field_info = adapter._convert_string_field(field)
        min_lengths = [m for m in field_info.metadata if hasattr(m, "min_length")]
        max_lengths = [m for m in field_info.metadata if hasattr(m, "max_length")]
        assert min_lengths == []
        assert max_lengths == []

    # --- Pattern constraint ---

    def test_pattern_mapped(self, adapter: PydanticAdapter):
        field = StringField(
            name="code",
            constraints={"required": True, "pattern": r"^[A-Z]{2}$"},
        )
        _, field_info = adapter._convert_string_field(field)
        patterns = [m.pattern for m in field_info.metadata if hasattr(m, "pattern")]
        assert r"^[A-Z]{2}$" in patterns

    def test_no_pattern_omits_pattern(self, adapter: PydanticAdapter):
        field = StringField(name="note", constraints={"required": True})
        _, field_info = adapter._convert_string_field(field)
        patterns = [m for m in field_info.metadata if hasattr(m, "pattern")]
        assert patterns == []

    # --- Metadata ---

    def test_field_name_stored_in_json_schema_extra(self, adapter: PydanticAdapter):
        field = StringField(name="country", constraints={"required": True})
        _, field_info = adapter._convert_string_field(field)
        assert field_info.json_schema_extra == {"name": "country"}

    def test_title_is_propagated(self, adapter: PydanticAdapter):
        field = StringField(
            name="country", title="Country Code", constraints={"required": True}
        )
        _, field_info = adapter._convert_string_field(field)
        assert field_info.title == "Country Code"

    def test_description_is_propagated(self, adapter: PydanticAdapter):
        field = StringField(
            name="country",
            description="ISO country code",
            constraints={"required": True},
        )
        _, field_info = adapter._convert_string_field(field)
        assert field_info.description == "ISO country code"

    # --- Enum constraint ---

    def test_enum_constraint_creates_validator(self, adapter: PydanticAdapter):
        field = StringField(
            name="status",
            constraints={"required": True, "enum": ["active", "inactive"]},
        )
        adapter._convert_string_field(field)
        assert "validate_enum_status" in adapter._validators

    def test_no_enum_constraint_skips_validator(self, adapter: PydanticAdapter):
        field = StringField(name="country", constraints={"required": True})
        adapter._convert_string_field(field)
        assert "validate_enum_country" not in adapter._validators


class TestDatetimeFieldConversion:
    """Test class for the datetime field conversion in PydanticAdapter."""

    @pytest.fixture
    def adapter(self, sample_schema):
        return PydanticAdapter(sample_schema)

    # --- Type mapping ---

    def test_returns_datetime_type(self, adapter: PydanticAdapter):
        field = DateTimeField(name="created_at", constraints={"required": True})
        python_type, _ = adapter._convert_datetime_field(field)
        assert python_type is datetime

    # --- Required / optional ---

    def test_required_field_has_no_default(self, adapter: PydanticAdapter):
        field = DateTimeField(name="created_at", constraints={"required": True})
        _, field_info = adapter._convert_datetime_field(field)
        assert field_info.is_required()

    def test_optional_field_defaults_to_none(self, adapter: PydanticAdapter):
        field = DateTimeField(name="created_at", constraints={"required": False})
        _, field_info = adapter._convert_datetime_field(field)
        assert field_info.default is None
        assert not field_info.is_required()

    # --- Minimum / maximum constraints ---

    def test_minimum_constraint_parsed_to_ge(self, adapter: PydanticAdapter):
        field = DateTimeField(
            name="created_at",
            format="%Y-%m-%d %H:%M",
            constraints={"required": True, "minimum": "2020-01-01 00:00"},
        )
        _, field_info = adapter._convert_datetime_field(field)
        ge_values = [m.ge for m in field_info.metadata if hasattr(m, "ge")]
        assert datetime(2020, 1, 1, 0, 0, tzinfo=UTC) in ge_values

    def test_maximum_constraint_parsed_to_le(self, adapter: PydanticAdapter):
        field = DateTimeField(
            name="created_at",
            format="%Y-%m-%d %H:%M",
            constraints={"required": True, "maximum": "2025-12-31 23:59"},
        )
        _, field_info = adapter._convert_datetime_field(field)
        le_values = [m.le for m in field_info.metadata if hasattr(m, "le")]
        assert datetime(2025, 12, 31, 23, 59, tzinfo=UTC) in le_values

    def test_both_min_and_max_constraints(self, adapter: PydanticAdapter):
        field = DateTimeField(
            name="created_at",
            format="%Y-%m-%d %H:%M",
            constraints={
                "required": True,
                "minimum": "2020-01-01 00:00",
                "maximum": "2025-12-31 23:59",
            },
        )
        _, field_info = adapter._convert_datetime_field(field)
        ge_values = [m.ge for m in field_info.metadata if hasattr(m, "ge")]
        le_values = [m.le for m in field_info.metadata if hasattr(m, "le")]
        assert datetime(2020, 1, 1, 0, 0, tzinfo=UTC) in ge_values
        assert datetime(2025, 12, 31, 23, 59, tzinfo=UTC) in le_values

    def test_no_constraints_omits_ge_le(self, adapter: PydanticAdapter):
        field = DateTimeField(name="created_at", constraints={"required": True})
        _, field_info = adapter._convert_datetime_field(field)
        ge_values = [m for m in field_info.metadata if hasattr(m, "ge")]
        le_values = [m for m in field_info.metadata if hasattr(m, "le")]
        assert ge_values == []
        assert le_values == []

    # --- Custom format ---

    def test_minimum_parsed_with_custom_format(self, adapter: PydanticAdapter):
        field = DateTimeField(
            name="created_at",
            format="%d/%m/%Y",
            constraints={"required": True, "minimum": "01/06/2023"},
        )
        _, field_info = adapter._convert_datetime_field(field)
        ge_values = [m.ge for m in field_info.metadata if hasattr(m, "ge")]
        assert datetime(2023, 6, 1, 0, 0, tzinfo=UTC) in ge_values

    def test_maximum_parsed_with_custom_format(self, adapter: PydanticAdapter):
        field = DateTimeField(
            name="created_at",
            format="%d/%m/%Y",
            constraints={"required": True, "maximum": "31/12/2025"},
        )
        _, field_info = adapter._convert_datetime_field(field)
        le_values = [m.le for m in field_info.metadata if hasattr(m, "le")]
        assert datetime(2025, 12, 31, 0, 0, tzinfo=UTC) in le_values

    # --- Parse datetime validator ---

    def test_datetime_validator_registered(self, adapter: PydanticAdapter):
        field = DateTimeField(name="created_at", constraints={"required": True})
        adapter._convert_datetime_field(field)
        assert "check_datetime_format_created_at" in adapter._validators

    def test_datetime_validator_unique_per_field(self, adapter: PydanticAdapter):
        field_a = DateTimeField(name="start_at", constraints={"required": True})
        field_b = DateTimeField(name="end_at", constraints={"required": True})
        adapter._convert_datetime_field(field_a)
        adapter._convert_datetime_field(field_b)
        assert "check_datetime_format_start_at" in adapter._validators
        assert "check_datetime_format_end_at" in adapter._validators

    # --- Metadata ---

    def test_field_name_stored_in_json_schema_extra(self, adapter: PydanticAdapter):
        field = DateTimeField(name="created_at", constraints={"required": True})
        _, field_info = adapter._convert_datetime_field(field)
        assert field_info.json_schema_extra == {"name": "created_at"}

    def test_title_is_propagated(self, adapter: PydanticAdapter):
        field = DateTimeField(
            name="created_at", title="Creation Time", constraints={"required": True}
        )
        _, field_info = adapter._convert_datetime_field(field)
        assert field_info.title == "Creation Time"

    def test_description_is_propagated(self, adapter: PydanticAdapter):
        field = DateTimeField(
            name="created_at",
            description="When the record was created",
            constraints={"required": True},
        )
        _, field_info = adapter._convert_datetime_field(field)
        assert field_info.description == "When the record was created"

    # --- Default format ---

    def test_uses_default_format(self, adapter: PydanticAdapter):
        """When no format is specified, the default %Y-%m-%d %H:%M is used."""
        field = DateTimeField(
            name="created_at",
            constraints={"required": True, "minimum": "2020-01-01 00:00"},
        )
        _, field_info = adapter._convert_datetime_field(field)
        ge_values = [m.ge for m in field_info.metadata if hasattr(m, "ge")]
        assert datetime(2020, 1, 1, 0, 0, tzinfo=UTC) in ge_values


class TestListFieldConversion:
    """Test class for the list field conversion in PydanticAdapter."""

    @pytest.fixture
    def adapter(self, sample_schema):
        return PydanticAdapter(sample_schema)

    # --- Type mapping ---

    def test_returns_list_of_str_type(self, adapter: PydanticAdapter):
        field = ListField(
            name="tags", itemType="string", constraints={"required": True}
        )
        python_type, _ = adapter._convert_list_field(field)
        assert python_type == list[str]

    def test_returns_list_of_int_type(self, adapter: PydanticAdapter):
        field = ListField(
            name="counts", itemType="integer", constraints={"required": True}
        )
        python_type, _ = adapter._convert_list_field(field)
        assert python_type == list[int]

    def test_returns_list_of_float_type(self, adapter: PydanticAdapter):
        field = ListField(
            name="scores", itemType="number", constraints={"required": True}
        )
        python_type, _ = adapter._convert_list_field(field)
        assert python_type == list[float]

    def test_returns_list_of_bool_type(self, adapter: PydanticAdapter):
        field = ListField(
            name="flags", itemType="boolean", constraints={"required": True}
        )
        python_type, _ = adapter._convert_list_field(field)
        assert python_type == list[bool]

    # --- Required / optional ---

    def test_required_field_has_no_default(self, adapter: PydanticAdapter):
        field = ListField(
            name="tags", itemType="string", constraints={"required": True}
        )
        _, field_info = adapter._convert_list_field(field)
        assert field_info.is_required()

    def test_optional_field_defaults_to_none(self, adapter: PydanticAdapter):
        field = ListField(
            name="tags", itemType="string", constraints={"required": False}
        )
        _, field_info = adapter._convert_list_field(field)
        assert field_info.default is None
        assert not field_info.is_required()

    # --- minLength / maxLength constraints ---

    def test_min_length_constraint(self, adapter: PydanticAdapter):
        field = ListField(
            name="tags",
            itemType="string",
            constraints={"required": True, "minLength": 1},
        )
        _, field_info = adapter._convert_list_field(field)
        min_lengths = [
            m.min_length for m in field_info.metadata if hasattr(m, "min_length")
        ]
        assert 1 in min_lengths

    def test_max_length_constraint(self, adapter: PydanticAdapter):
        field = ListField(
            name="tags",
            itemType="string",
            constraints={"required": True, "maxLength": 10},
        )
        _, field_info = adapter._convert_list_field(field)
        max_lengths = [
            m.max_length for m in field_info.metadata if hasattr(m, "max_length")
        ]
        assert 10 in max_lengths

    def test_both_min_and_max_length_constraints(self, adapter: PydanticAdapter):
        field = ListField(
            name="tags",
            itemType="string",
            constraints={"required": True, "minLength": 1, "maxLength": 10},
        )
        _, field_info = adapter._convert_list_field(field)
        min_lengths = [
            m.min_length for m in field_info.metadata if hasattr(m, "min_length")
        ]
        max_lengths = [
            m.max_length for m in field_info.metadata if hasattr(m, "max_length")
        ]
        assert 1 in min_lengths
        assert 10 in max_lengths

    def test_no_constraints_omits_min_max_length(self, adapter: PydanticAdapter):
        field = ListField(
            name="tags", itemType="string", constraints={"required": True}
        )
        _, field_info = adapter._convert_list_field(field)
        min_lengths = [m for m in field_info.metadata if hasattr(m, "min_length")]
        max_lengths = [m for m in field_info.metadata if hasattr(m, "max_length")]
        assert min_lengths == []
        assert max_lengths == []


class TestToPydanticModel:
    """Test class for the to_pydantic_model method of PydanticAdapter."""

    # --- Model creation ---

    def test_returns_a_basemodel_subclass(self, sample_schema):
        Model = PydanticAdapter(sample_schema).convert()
        assert issubclass(Model, BaseModel)

    def test_default_model_name(self, sample_schema):
        Model = PydanticAdapter(sample_schema).convert()
        assert Model.__name__ == "ConvertedModel"

    def test_custom_model_name(self, sample_schema):
        Model = PydanticAdapter(sample_schema).convert(name="MyModel")
        assert Model.__name__ == "MyModel"

    def test_custom_base_class(self, sample_schema):
        class CustomBase(BaseModel):
            pass

        Model = PydanticAdapter(sample_schema).convert(base_class=CustomBase)
        assert issubclass(Model, CustomBase)

    # --- Field registration ---

    def test_all_supported_fields_registered(self, sample_schema):
        Model = PydanticAdapter(sample_schema).convert()
        assert set(Model.model_fields.keys()) == {"value", "year", "country"}

    def test_integer_field_registered(self, sample_schema):
        Model = PydanticAdapter(sample_schema).convert()
        assert "year" in Model.model_fields

    def test_number_field_registered(self, sample_schema):
        Model = PydanticAdapter(sample_schema).convert()
        assert "value" in Model.model_fields

    def test_string_field_registered(self, sample_schema):
        Model = PydanticAdapter(sample_schema).convert()
        assert "country" in Model.model_fields

    def test_datetime_field_registered(self):
        schema = TableSchema.model_validate(
            {
                "fields": [
                    {
                        "name": "created_at",
                        "type": "datetime",
                        "constraints": {"required": True},
                    }
                ]
            }
        )
        Model = PydanticAdapter(schema).convert()
        assert "created_at" in Model.model_fields

    def test_list_field_registered(self):
        schema = TableSchema.model_validate(
            {
                "fields": [
                    {
                        "name": "tags",
                        "type": "list",
                        "itemType": "string",
                        "constraints": {"required": True},
                    }
                ]
            }
        )
        Model = PydanticAdapter(schema).convert()
        assert "tags" in Model.model_fields

    # --- Validators passed through ---

    def test_validators_attached_when_enum_present(self):
        schema = TableSchema.model_validate(
            {
                "fields": [
                    {
                        "name": "status",
                        "type": "integer",
                        "constraints": {"required": True, "enum": [1, 2, 3]},
                    }
                ]
            }
        )
        adapter = PydanticAdapter(schema)
        adapter.convert()
        assert "validate_enum_status" in adapter._validators

    def test_datetime_validator_attached(self):
        schema = TableSchema.model_validate(
            {
                "fields": [
                    {
                        "name": "ts",
                        "type": "datetime",
                        "constraints": {"required": True},
                    }
                ]
            }
        )
        adapter = PydanticAdapter(schema)
        adapter.convert()
        assert "check_datetime_format_ts" in adapter._validators

    # --- convert_schema_to_pydantic pass-through ---

    def test_convert_schema_to_pydantic_returns_model(self, sample_schema):
        Model = convert_schema_to_pydantic(sample_schema)
        assert issubclass(Model, BaseModel)
        assert set(Model.model_fields.keys()) == {"value", "year", "country"}

    def test_convert_schema_to_pydantic_forwards_name(self, sample_schema):
        Model = convert_schema_to_pydantic(sample_schema, name="CustomName")
        assert Model.__name__ == "CustomName"

    def test_convert_schema_to_pydantic_forwards_base_class(self, sample_schema):
        class CustomBase(BaseModel):
            pass

        Model = convert_schema_to_pydantic(sample_schema, base_class=CustomBase)
        assert issubclass(Model, CustomBase)

    def test_unsupported_field_type_raises(self, sample_schema):
        adapter = PydanticAdapter(sample_schema)
        fake_field = MagicMock()
        fake_field.type = "boolean"

        with patch.object(TableSchema, "field_iterator", return_value=[fake_field]):
            with pytest.raises(NotImplementedError, match="boolean"):
                adapter.convert()
