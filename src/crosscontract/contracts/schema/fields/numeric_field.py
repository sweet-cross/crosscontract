from typing import Generic, Literal, TypeVar

from pydantic import Field

from .base import BaseConstraint, BaseField

# Define a TypeVar for the numeric type
T = TypeVar("T", int, float)


class NumericConstraint(BaseConstraint, Generic[T]):
    minimum: T | None = None
    maximum: T | None = None
    enum: list[T] | None = Field(default=None, min_length=1)


class IntegerField(BaseField):
    """
    A class representing an integer field in a frictionless schema.
    This class can be extended to define specific integer fields.
    """

    type: Literal["integer"] = Field(
        default="integer",
        description="The type of the field, which is 'integer' for this class.",
    )

    constraints: NumericConstraint[int] = Field(default_factory=NumericConstraint[int])


class NumberField(BaseField):
    """
    A class representing a number field in a frictionless schema.
    This class can be extended to define specific number fields.
    """

    type: Literal["number"] = Field(
        default="number",
        description="The type of the field, which is 'number' for this class.",
    )

    constraints: NumericConstraint[float] = Field(
        default_factory=NumericConstraint[float]
    )
