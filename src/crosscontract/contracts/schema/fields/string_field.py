from typing import Any, Literal

import pandera.pandas as pa
from pydantic import Field
from sqlalchemy import Column, String

from .base import BaseConstraint, BaseField


class StringConstraint(BaseConstraint):
    """
    Constraint for string fields.
    This class can be extended to define specific string constraints.
    """

    pattern: str | None = Field(
        default=None,
        description=(
            "A regular expression pattern to test each value of the property "
            "against, where a truthy response indicates validity."
        ),
    )

    minLength: int | None = Field(
        default=None,
        description="An integer that specifies the minimum length of a value.",
    )

    maxLength: int | None = Field(
        default=None,
        description="An integer that specifies the maximum length of a value.",
    )

    enum: list[str] | None = Field(default=None, min_length=1)

    def get_pydantic_field_kwargs(self) -> dict[str, Any]:
        """Returns the pydantic field kwargs for the string constraint."""
        kwargs = super().get_pydantic_field_kwargs()

        # Handle pattern constraint
        if self.pattern is not None:
            kwargs["regex"] = self.pattern

        # Handle minLength and maxLength constraints
        if self.minLength is not None:
            kwargs["min_length"] = self.minLength
        if self.maxLength is not None:
            kwargs["max_length"] = self.maxLength

        return kwargs

    def get_pandera_kwargs(self) -> dict[str, Any]:
        """Returns the keyword arguments to create a pandera Column for
        this constraint."""
        kwargs = super().get_pandera_kwargs()

        # Handle pattern constraint
        if self.pattern is not None:
            kwargs["regex"] = self.pattern

        # Handle minLength and maxLength constraints
        if self.minLength or self.maxLength:
            kwargs["checks"] = kwargs.get("checks", [])
            kwargs["checks"].append(
                pa.Check.str_length(min_value=self.minLength, max_value=self.maxLength)
            )
        return kwargs


class StringField(BaseField):
    """
    A class representing a string field in a frictionless schema.
    This class can be extended to define specific string fields.
    """

    type: Literal["string"] = Field(
        default="string",
        description="The type of the field, which is 'string' for this class.",
    )
    constraints: StringConstraint = Field(
        default_factory=lambda: StringConstraint(),
        description="Constraints for the `string` field",
    )

    @property
    def python_type(self) -> type:  # type: ignore
        """Returns the Python type of the field."""
        return str

    def to_sqlalchemy_column(self) -> Column:
        """Returns the SQLAlchemy Column for the string field."""
        c = Column(
            self.name,
            String,
            nullable=not self.constraints.required if self.constraints else True,
        )
        return c
