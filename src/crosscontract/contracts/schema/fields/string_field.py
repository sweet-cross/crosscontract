from typing import Literal

from pydantic import Field

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
        default_factory=StringConstraint,
        description="Constraints for the `string` field",
    )
