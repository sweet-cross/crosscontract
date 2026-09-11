import pandas as pd
import pandera.pandas as pa
import pytest
from pandera import DateTime

from crosscontract.contracts.schema.adapters.pandera_pandas.field_convertors import (
    DateTimeFieldConverter,
    ListFieldConverter,
    NumericFieldConverter,
    StringFieldConverter,
    get_field_converter,
)
from crosscontract.contracts.schema.fields import (
    DateTimeField,
    IntegerField,
    ListField,
    NumberField,
    StringField,
)

# These port the cases from
# src/tests/contracts/schema/adapters/pandera/test_pandera_pandas_adapter.py,
# which covered the same conversions as methods on the adapter. Only the
# construction is re-pointed: a converter holds its field, so there is no
# adapter fixture and no field argument.


# ---------------------------------------------------------------------------
# get_kwargs: shared column properties
# ---------------------------------------------------------------------------


class TestGetKwargs:
    """Test the shared kwargs assembly on the base converter."""

    def test_required_field_is_not_nullable(self):
        field = StringField(name="label", constraints={"required": True})
        kwargs = StringFieldConverter(field).get_kwargs()
        assert kwargs["required"] is True
        assert "nullable" not in kwargs

    def test_optional_field_is_nullable(self):
        field = StringField(name="label", constraints={"required": False})
        kwargs = StringFieldConverter(field).get_kwargs()
        assert kwargs["required"] is False
        assert kwargs["nullable"] is True

    def test_name_and_dtype_are_set(self):
        field = IntegerField(name="age")
        kwargs = NumericFieldConverter(field).get_kwargs()
        assert kwargs["name"] == "age"
        assert kwargs["dtype"] == "Int64"

    def test_enum_constraint_adds_isin_check(self):
        field = StringField(
            name="color", constraints={"enum": ["red", "green", "blue"]}
        )
        kwargs = StringFieldConverter(field).get_kwargs()
        assert len(kwargs["checks"]) == 1


# ---------------------------------------------------------------------------
# NumericFieldConverter
# ---------------------------------------------------------------------------


class TestNumericFieldConverter:
    """Test numeric field conversion."""

    def test_integer_field_uses_int64(self):
        col = NumericFieldConverter(IntegerField(name="age")).convert()
        assert str(col.dtype) == "Int64"

    def test_number_field_uses_float64(self):
        col = NumericFieldConverter(NumberField(name="score")).convert()
        assert str(col.dtype) == "float64"

    def test_no_constraints_produces_no_checks(self):
        col = NumericFieldConverter(IntegerField(name="age")).convert()
        assert col.checks == []

    def test_minimum_adds_ge_check(self):
        field = IntegerField(name="age", constraints={"minimum": 5})
        col = NumericFieldConverter(field).convert()
        assert len(col.checks) == 1

    def test_maximum_adds_le_check(self):
        field = IntegerField(name="age", constraints={"maximum": 10})
        col = NumericFieldConverter(field).convert()
        assert len(col.checks) == 1

    def test_both_constraints_add_two_checks(self):
        field = IntegerField(name="age", constraints={"minimum": 5, "maximum": 10})
        col = NumericFieldConverter(field).convert()
        assert len(col.checks) == 2

    def test_minimum_zero_is_not_skipped(self):
        field = IntegerField(name="age", constraints={"minimum": 0})
        col = NumericFieldConverter(field).convert()
        assert len(col.checks) == 1


# ---------------------------------------------------------------------------
# StringFieldConverter
# ---------------------------------------------------------------------------


class TestStringFieldConverter:
    """Test string field conversion."""

    def test_no_constraints_produces_no_checks(self):
        col = StringFieldConverter(StringField(name="label")).convert()
        assert col.checks == []

    def test_pattern_becomes_a_value_check(self):
        """The pattern constrains the values, not the column name — `regex` on a
        pandera Column means the name is a pattern, which is not what this is."""
        field = StringField(name="code", constraints={"pattern": r"^[A-Z]+$"})
        col = StringFieldConverter(field).convert()
        assert col.checks[0].name == "str_matches"
        assert not col.regex

    @pytest.mark.parametrize(
        ("pattern", "value", "passes"),
        [
            pytest.param(r"^[A-Z]+$", "AB", True, id="anchored_full"),
            pytest.param(r"^[A-Z]+$", "ABxy", False, id="anchored_trailing"),
            pytest.param(r"[A-Z]+", "AB", True, id="unanchored_full"),
            pytest.param(r"[A-Z]+", "ABxy", False, id="unanchored_trailing"),
            pytest.param(r"ab|cd", "cd", True, id="alternation_full"),
            pytest.param(r"ab|cd", "cdx", False, id="alternation_trailing"),
        ],
    )
    def test_pattern_must_match_the_whole_value(
        self, pattern: str, value: str, passes: bool
    ):
        """Frictionless patterns follow XML Schema regex syntax, which matches
        the whole value, so an unanchored pattern still rejects a trailing
        remainder."""
        field = StringField(name="code", constraints={"pattern": pattern})
        check = StringFieldConverter(field).convert().checks[0]
        assert bool(check(pd.Series([value])).check_passed) is passes

    @pytest.mark.parametrize(
        ("required", "value", "passes"),
        [
            pytest.param(False, "AB", True, id="optional_match"),
            pytest.param(False, "", True, id="optional_blank"),
            pytest.param(False, None, True, id="optional_null"),
            pytest.param(False, "ab", False, id="optional_violation"),
            pytest.param(True, "AB", True, id="required_match"),
            pytest.param(True, "", False, id="required_blank"),
            pytest.param(True, "ab", False, id="required_violation"),
        ],
    )
    def test_a_blank_passes_the_pattern_only_when_optional(
        self, required: bool, value: str | None, passes: bool
    ):
        """A tabular source carries no null of its own, so a blank cell arrives
        as `""` and means the same thing — on a non-required field. A required
        one has no null to mean, so its pattern still rejects a blank."""
        field = StringField(
            name="code",
            constraints={"pattern": r"^[A-Z]+$", "required": required},
        )
        schema = pa.DataFrameSchema({"code": StringFieldConverter(field).convert()})
        df = pd.DataFrame({"code": pd.Series([value], dtype="object")})
        if passes:
            assert len(schema.validate(df, lazy=True)) == 1
        else:
            with pytest.raises(pa.errors.SchemaErrors):
                schema.validate(df, lazy=True)

    def test_min_length_only(self):
        field = StringField(name="label", constraints={"minLength": 5})
        col = StringFieldConverter(field).convert()
        assert len(col.checks) == 1
        assert col.checks[0]._check_kwargs["min_value"] == 5
        assert col.checks[0]._check_kwargs["max_value"] is None

    def test_max_length_only(self):
        field = StringField(name="label", constraints={"maxLength": 10})
        col = StringFieldConverter(field).convert()
        assert len(col.checks) == 1
        assert col.checks[0]._check_kwargs["min_value"] is None
        assert col.checks[0]._check_kwargs["max_value"] == 10

    def test_both_length_constraints(self):
        field = StringField(name="label", constraints={"minLength": 5, "maxLength": 10})
        col = StringFieldConverter(field).convert()
        assert len(col.checks) == 1
        assert col.checks[0]._check_kwargs["min_value"] == 5
        assert col.checks[0]._check_kwargs["max_value"] == 10


# ---------------------------------------------------------------------------
# ListFieldConverter
# ---------------------------------------------------------------------------


class TestListFieldConverter:
    """Test list field conversion."""

    def test_no_constraints_produces_no_checks(self):
        field = ListField(name="tags", itemType="string")
        col = ListFieldConverter(field).convert()
        assert col.checks == []

    def test_min_length_adds_check(self):
        field = ListField(name="tags", itemType="string", constraints={"minLength": 2})
        col = ListFieldConverter(field).convert()
        assert len(col.checks) == 1

    def test_max_length_adds_check(self):
        field = ListField(name="tags", itemType="string", constraints={"maxLength": 10})
        col = ListFieldConverter(field).convert()
        assert len(col.checks) == 1

    def test_both_length_constraints_add_two_checks(self):
        field = ListField(
            name="tags",
            itemType="string",
            constraints={"minLength": 2, "maxLength": 10},
        )
        col = ListFieldConverter(field).convert()
        assert len(col.checks) == 2

    def test_unsupported_item_type_raises(self):
        """`itemType` is a `Literal`, so pydantic rejects a bad value at
        construction. `BaseField` does not set `validate_assignment`, so
        assigning one afterwards reaches the guard."""
        field = ListField(name="tags", itemType="string")
        field.itemType = "bogus"  # type: ignore[assignment]
        with pytest.raises(ValueError):
            ListFieldConverter(field).get_pandera_type()


# ---------------------------------------------------------------------------
# DateTimeFieldConverter
# ---------------------------------------------------------------------------


class TestDateTimeFieldConverter:
    """Test datetime field conversion."""

    def test_dtype_is_datetime(self):
        col = DateTimeFieldConverter(DateTimeField(name="created_at")).convert()
        assert isinstance(col.dtype, DateTime)

    def test_no_constraints_produces_no_checks(self):
        col = DateTimeFieldConverter(DateTimeField(name="created_at")).convert()
        assert col.checks == []

    def test_minimum_adds_check(self):
        field = DateTimeField(
            name="created_at", constraints={"minimum": "2023-01-01 00:00"}
        )
        col = DateTimeFieldConverter(field).convert()
        assert len(col.checks) == 1

    def test_maximum_adds_check(self):
        field = DateTimeField(
            name="created_at", constraints={"maximum": "2023-12-31 00:00"}
        )
        col = DateTimeFieldConverter(field).convert()
        assert len(col.checks) == 1

    def test_both_constraints_add_two_checks(self):
        field = DateTimeField(
            name="created_at",
            constraints={
                "minimum": "2023-01-01 00:00",
                "maximum": "2023-12-31 00:00",
            },
        )
        col = DateTimeFieldConverter(field).convert()
        assert len(col.checks) == 2


# ---------------------------------------------------------------------------
# get_field_converter: dispatch
# ---------------------------------------------------------------------------


class TestGetFieldConverter:
    """Test that each field type reaches its own converter."""

    @pytest.mark.parametrize(
        ("field", "expected"),
        [
            pytest.param(IntegerField(name="age"), NumericFieldConverter, id="integer"),
            pytest.param(NumberField(name="score"), NumericFieldConverter, id="number"),
            pytest.param(StringField(name="label"), StringFieldConverter, id="string"),
            pytest.param(
                DateTimeField(name="created_at"),
                DateTimeFieldConverter,
                id="datetime",
            ),
            pytest.param(
                ListField(name="tags", itemType="string"),
                ListFieldConverter,
                id="list",
            ),
        ],
    )
    def test_field_type_selects_its_converter(self, field, expected):
        converter = get_field_converter(field)
        assert isinstance(converter, expected)
        assert converter.field is field
