import pandera as pa
from sqlalchemy import ARRAY

from crosscontract.contracts.schema.fields.list_field import (
    MAP_ITEM_TYPES_PYTHON,
    ListConstraint,
    ListField,
)


class TestListConstraint:
    def test_neither_min_nor_max_length_constraint(self):
        constraint = ListConstraint()
        kwargs = constraint.get_pydantic_field_kwargs()
        assert "min_length" not in kwargs
        assert "max_length" not in kwargs

    def test_min_length_constraint(self):
        constraint = ListConstraint(minLength=2)
        kwargs = constraint.get_pydantic_field_kwargs()
        assert kwargs["min_length"] == 2
        assert "max_length" not in kwargs

    def test_max_length_constraint(self):
        constraint = ListConstraint(maxLength=10)
        kwargs = constraint.get_pydantic_field_kwargs()
        assert kwargs["max_length"] == 10
        assert "min_length" not in kwargs

    def test_both_min_and_max_length_constraint(self):
        constraint = ListConstraint(minLength=2, maxLength=10)
        kwargs = constraint.get_pydantic_field_kwargs()
        assert kwargs["min_length"] == 2
        assert kwargs["max_length"] == 10

    def test_pandera_kwargs_no_length_constraints(self):
        constraint = ListConstraint()
        kwargs = constraint.get_pandera_kwargs()
        assert kwargs["checks"] == []

    def test_pandera_kwargs_min_length_constraint(self):
        constraint = ListConstraint(minLength=2)
        kwargs = constraint.get_pandera_kwargs()
        assert len(kwargs["checks"]) == 1
        check = kwargs["checks"][0]
        assert isinstance(check, pa.Check)

    def test_pandera_kwargs_max_length_constraint(self):
        constraint = ListConstraint(maxLength=10)
        kwargs = constraint.get_pandera_kwargs()
        assert len(kwargs["checks"]) == 1
        check = kwargs["checks"][0]
        assert isinstance(check, pa.Check)

    def test_pandera_kwargs_both_length_constraints(self):
        constraint = ListConstraint(minLength=2, maxLength=10)
        kwargs = constraint.get_pandera_kwargs()
        assert len(kwargs["checks"]) == 2
        checks = kwargs["checks"]
        assert isinstance(checks[0], pa.Check)
        assert isinstance(checks[1], pa.Check)


class TestListField:
    def test_neither_min_nor_max_length_constraint(self):
        field = ListField(name="test_field")
        kwargs = field.get_pydantic_field_kwargs()
        assert "min_length" not in kwargs
        assert "max_length" not in kwargs

    def test_type_hints(self):
        # by default values are not required
        for item_type, python_type in MAP_ITEM_TYPES_PYTHON.items():
            field = ListField(name="test_field", itemType=item_type)
            assert field.get_type_hint() == list[python_type] | None
        # required case
        for item_type, python_type in MAP_ITEM_TYPES_PYTHON.items():
            field = ListField(
                name="test_field",
                itemType=item_type,
                constraints=ListConstraint(required=True),
            )
            assert field.get_type_hint() == list[python_type]

    def test_min_length_constraint(self):
        constraint = ListConstraint(minLength=2)
        field = ListField(name="test_field", constraints=constraint)
        kwargs = field.get_pydantic_field_kwargs()
        assert kwargs["min_length"] == 2
        assert "max_length" not in kwargs

    def test_max_length_constraint(self):
        constraint = ListConstraint(maxLength=10)
        field = ListField(name="test_field", constraints=constraint)
        kwargs = field.get_pydantic_field_kwargs()
        assert kwargs["max_length"] == 10
        assert "min_length" not in kwargs

    def test_both_min_and_max_length_constraint(self):
        constraint = ListConstraint(minLength=2, maxLength=10)
        field = ListField(name="test_field", constraints=constraint)
        kwargs = field.get_pydantic_field_kwargs()
        assert kwargs["min_length"] == 2
        assert kwargs["max_length"] == 10

    def test_list_field_to_column(self):
        field = ListField(name="test_field")
        column = field.to_sqlalchemy_column()
        assert column.name == "test_field"
        assert isinstance(column.type, ARRAY)
        assert column.nullable

    def test_list_field_to_column_required(self):
        field = ListField(name="test_field", constraints=ListConstraint(required=True))
        column = field.to_sqlalchemy_column()
        assert column.name == "test_field"
        assert isinstance(column.type, ARRAY)
        assert not column.nullable
