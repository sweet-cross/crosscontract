import pandera as pa
from sqlalchemy import String

from crosscontract.contracts.schema.fields.string_field import (
    StringConstraint,
    StringField,
)


class TestStringConstraint:
    def test_given_pattern(self):
        constraint = StringConstraint(pattern=r"^[A-Z]+$")
        kwargs = constraint.get_pydantic_field_kwargs()
        assert kwargs["regex"] == r"^[A-Z]+$"

    def test_minLength_constraint(self):
        constraint = StringConstraint(minLength=5)
        kwargs = constraint.get_pydantic_field_kwargs()
        assert kwargs["min_length"] == 5
        assert "max_length" not in kwargs

    def test_maxLength_constraint(self):
        constraint = StringConstraint(maxLength=10)
        kwargs = constraint.get_pydantic_field_kwargs()
        assert kwargs["max_length"] == 10
        assert "min_length" not in kwargs


class TestStringField:
    def test_given_pattern(self):
        constraint = StringConstraint(pattern=r"^[A-Z]+$")
        field = StringField(name="test_field", constraints=constraint)
        kwargs = field.get_pydantic_field_kwargs()
        assert kwargs["regex"] == r"^[A-Z]+$"

    def test_minLength_constraint(self):
        constraint = StringConstraint(minLength=5)
        field = StringField(name="test_field", constraints=constraint)
        kwargs = field.get_pydantic_field_kwargs()
        assert kwargs["min_length"] == 5
        assert "max_length" not in kwargs

    def test_maxLength_constraint(self):
        constraint = StringConstraint(maxLength=10)
        field = StringField(name="test_field", constraints=constraint)
        kwargs = field.get_pydantic_field_kwargs()
        assert kwargs["max_length"] == 10
        assert "min_length" not in kwargs


class TestPanderaStringField:
    def test_given_pattern(self):
        constraint = StringConstraint(pattern=r"^[A-Z]+$")
        field = StringField(name="test_field", constraints=constraint)
        kwargs = field.get_pandera_kwargs()
        assert kwargs["regex"] == r"^[A-Z]+$"

    def test_minLength_constraint(self):
        constraint = StringConstraint(minLength=5)
        field = StringField(name="test_field", constraints=constraint)
        kwargs = field.get_pandera_kwargs()
        assert len(kwargs["checks"]) == 1
        check = kwargs["checks"][0]
        assert isinstance(check, pa.Check)
        assert check._check_kwargs["min_value"] == 5
        assert check._check_kwargs["max_value"] is None

    def test_maxLength_constraint(self):
        constraint = StringConstraint(maxLength=10)
        field = StringField(name="test_field", constraints=constraint)
        kwargs = field.get_pandera_kwargs()
        assert len(kwargs["checks"]) == 1
        check = kwargs["checks"][0]
        assert isinstance(check, pa.Check)
        assert check._check_kwargs["min_value"] is None
        assert check._check_kwargs["max_value"] == 10

    def test_minLength_and_maxLength_constraint(self):
        constraint = StringConstraint(minLength=5, maxLength=10)
        field = StringField(name="test_field", constraints=constraint)
        kwargs = field.get_pandera_kwargs()
        assert len(kwargs["checks"]) == 1
        check = kwargs["checks"][0]
        assert isinstance(check, pa.Check)
        assert check._check_kwargs["min_value"] == 5
        assert check._check_kwargs["max_value"] == 10


class TestToColumn:
    def test_field_to_column(self):
        field = StringField(name="test_field")
        column = field.to_sqlalchemy_column()
        assert column.name == "test_field"
        assert isinstance(column.type, String)
        assert column.nullable

    def test_string_field_to_column_required(self):
        field = StringField(
            name="test_field", constraints=StringConstraint(required=True)
        )
        column = field.to_sqlalchemy_column()
        assert column.name == "test_field"
        assert isinstance(column.type, String)
        assert not column.nullable
