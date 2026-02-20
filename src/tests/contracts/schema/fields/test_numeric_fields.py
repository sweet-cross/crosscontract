import pandera as pa

from crosscontract.contracts.schema.fields.numeric_field import (
    IntegerField,
    NumericConstraint,
)


class MyNumericConstraint(NumericConstraint[int]):
    """Concrete implementation for testing purposes."""

    pass


class MyFloatConstraint(NumericConstraint[float]):
    """Concrete implementation for testing purposes."""

    pass


class TestPanderaKwargs:
    def test_no_ge_or_le_constraint(self):
        field = IntegerField(name="test_field")
        kwargs = field.get_pandera_kwargs()
        assert kwargs["checks"] == []

    def test_both_ge_and_le_constraint(self):
        constraint = MyNumericConstraint(minimum=5, maximum=10)
        field = IntegerField(name="test_field", constraints=constraint)
        kwargs = field.get_pandera_kwargs()
        assert len(kwargs["checks"]) == 2
        checks = kwargs["checks"]
        assert isinstance(checks[0], pa.Check)
        assert isinstance(checks[1], pa.Check)

    def test_only_le_constraint(self):
        constraint = MyNumericConstraint(maximum=10)
        field = IntegerField(name="test_field", constraints=constraint)
        kwargs = field.get_pandera_kwargs()
        assert len(kwargs["checks"]) == 1
        check = kwargs["checks"][0]
        assert isinstance(check, pa.Check)

    def test_only_ge_constraint(self):
        constraint = MyNumericConstraint(minimum=5)
        field = IntegerField(name="test_field", constraints=constraint)
        kwargs = field.get_pandera_kwargs()
        assert len(kwargs["checks"]) == 1
        check = kwargs["checks"][0]
        assert isinstance(check, pa.Check)
