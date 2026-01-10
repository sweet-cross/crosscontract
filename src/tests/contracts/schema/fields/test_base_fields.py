from typing import Any, Literal

import pandera.pandas as pa
from pydantic import Field

from crosscontract.contracts.schema.fields.base import (
    BaseConstraint,
    BaseField,
)


class MyStringConstraint(BaseConstraint):
    """Concrete implementation for testing purposes."""

    enum: set[str] | None = Field(default=None, min_length=1)

    def get_pydantic_field_kwargs(self) -> dict[str, Any]:
        return super().get_pydantic_field_kwargs()

    def get_pandera_kwargs(self):
        return super().get_pandera_kwargs()


class MyStringField(BaseField):
    """Concrete implementation for testing purposes."""

    constraints: MyStringConstraint = Field(default_factory=MyStringConstraint)

    @property
    def python_type(self) -> type:
        return str

    def to_sqlalchemy_column(self):
        return None


class TestFieldTypeHints:
    def test_no_enum_not_required(self):
        field = MyStringField(name="test_field")
        type_hint = field.get_type_hint()
        assert type_hint == str | None

    def test_no_enum_not_required_w_constraint(self):
        constraint = MyStringConstraint(required=False)
        field = MyStringField(name="test_field", constraints=constraint)
        type_hint = field.get_type_hint()
        assert type_hint == str | None

    def test_enum_not_required(self):
        constraint = MyStringConstraint(required=False, enum={"option1", "option2"})
        field = MyStringField(name="test_field", constraints=constraint)
        type_hint = field.get_type_hint()
        expected = Literal["option1", "option2"] | None
        assert type_hint == expected

    def test_no_enum_required(self):
        constraint = MyStringConstraint(required=True, enum=None)
        field = MyStringField(name="test_field", constraints=constraint)
        type_hint = field.get_type_hint()
        assert type_hint is str

    def test_enum_required(self):
        constraint = MyStringConstraint(required=True, enum={"option1", "option2"})
        field = MyStringField(name="test_field", constraints=constraint)
        type_hint = field.get_type_hint()
        expected = Literal["option1", "option2"]
        assert type_hint == expected


class TestFieldKwargs:
    def test_required_is_true(self):
        constraint = MyStringConstraint(required=True)
        kwargs = constraint.get_pydantic_field_kwargs()
        assert kwargs.get("default") is None

    def test_required_is_false(self):
        constraint = MyStringConstraint(required=False)
        kwargs = constraint.get_pydantic_field_kwargs()
        assert kwargs["default"] is None

    def test_enum_is_given(self):
        constraint = MyStringConstraint(enum={"option1", "option2"})
        kwargs = constraint.get_pydantic_field_kwargs()
        expected_enum = {"option1", "option2"}
        assert set(kwargs["json_schema_extra"]["enum"]) == expected_enum

    def test_unique_is_true(self):
        constraint = MyStringConstraint(unique=True)
        kwargs = constraint.get_pydantic_field_kwargs()
        assert kwargs["json_schema_extra"]["unique"] is True


class TestPanderaKwargs:
    def test_required_is_true(self):
        field = MyStringField(
            name="test_field", constraints=MyStringConstraint(required=True)
        )
        kwargs = field.get_pandera_kwargs()
        assert kwargs.get("nullable") is None

    def test_required_is_false(self):
        field = MyStringField(
            name="test_field", constraints=MyStringConstraint(required=False)
        )
        kwargs = field.get_pandera_kwargs()
        assert kwargs["nullable"] is True

    def test_enum_is_given(self):
        field = MyStringField(
            name="test_field",
            constraints=MyStringConstraint(enum={"option1", "option2"}),
        )
        kwargs = field.get_pandera_kwargs()
        assert len(kwargs["checks"]) == 1
        check = kwargs["checks"][0]
        assert isinstance(check, pa.Check)
        expected_enum = {"option1", "option2"}
        assert set(check._check_kwargs["allowed_values"]) == expected_enum

    def test_unique_is_true(self):
        field = MyStringField(
            name="test_field", constraints=MyStringConstraint(unique=True)
        )
        kwargs = field.get_pandera_kwargs()
        assert kwargs["unique"] is True
