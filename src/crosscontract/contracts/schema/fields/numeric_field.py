from typing import Literal, TypeVar

import pandera.pandas as pa
from pydantic import Field
from sqlalchemy import Column, Float, Integer

from .base import BaseConstraint, BaseField

# Define a TypeVar for the numeric type
T = TypeVar("T", int, float)


class NumericConstraint[T](BaseConstraint):
    minimum: T | None = None
    maximum: T | None = None
    enum: list[T] | None = Field(default=None, min_length=1)

    def get_pydantic_field_kwargs(self):
        """Returns the pydantic field kwargs for the numeric constraint."""
        kwargs = super().get_pydantic_field_kwargs()

        # Handle minimum and maximum constraints
        if self.minimum is not None:
            kwargs["ge"] = self.minimum  # Greater than or equal to
        if self.maximum is not None:
            kwargs["le"] = self.maximum  # Less than or equal to

        return kwargs

    def get_pandera_kwargs(self):
        """Returns the keyword arguments to create a pandera Column for
        this constraint."""
        kwargs = super().get_pandera_kwargs()

        # Handle minimum and maximum constraints
        if self.minimum is not None:
            kwargs["checks"].append(pa.Check.ge(self.minimum))
        if self.maximum is not None:
            kwargs["checks"].append(pa.Check.le(self.maximum))

        return kwargs


class IntegerField(BaseField):
    """
    A class representing an integer field in a frictionless schema.
    This class can be extended to define specific integer fields.
    """

    type: Literal["integer"] = Field(
        default="integer",
        description="The type of the field, which is 'integer' for this class.",
    )

    constraints: NumericConstraint[int] = Field(
        default_factory=lambda: NumericConstraint[int]()
    )

    @property
    def python_type(self) -> type:  # type: ignore
        """Returns the Python type of the field."""
        return int

    @property
    def pandera_type(self) -> str:  # type: ignore
        """Returns the Pandera type of the field."""
        return "Int64"

    def to_sqlalchemy_column(self):
        return Column(
            self.name,
            Integer,
            nullable=not self.constraints.required if self.constraints else True,
        )


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
        default_factory=lambda: NumericConstraint[float]()
    )

    @property
    def python_type(self) -> type:  # type: ignore
        """Returns the Python type of the field."""
        return float

    def to_sqlalchemy_column(self):
        return Column(
            self.name,
            Float,
            nullable=not self.constraints.required if self.constraints else True,
        )
