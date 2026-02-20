from abc import ABC

from pydantic import BaseModel, ConfigDict, Field

from crosscontract.contracts.valid_items import (
    ValidFieldName,
    max_field_name_length,
    valid_field_name_pattern,
)


class BaseConstraint(BaseModel, ABC):
    """
    Base class for constraints.
    This class can be extended to define specific constraints.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    required: bool = Field(
        default=False,
        description="Indicates whether a property must have a value for each instance.",
    )

    unique: bool | None = Field(
        default=False,
        description="When `true`, each value for the property `MUST` be unique.",
    )


class BaseField(BaseModel, ABC):
    """
    Base class for frictionless fields.
    This class can be extended to define specific frictionless fields.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    name: ValidFieldName = Field(
        description=(
            "The name of the field, which must be unique within the schema."
            f" It must match the pattern {valid_field_name_pattern} and cannot"
            f" exceed {max_field_name_length} characters."
        ),
    )
    title: str | None = Field(
        default=None,
        description="A human-readable title for the field.",
    )
    description: str | None = Field(
        default=None, description="A human-readable description of the field."
    )

    constraints: BaseConstraint = Field(
        description="Constraints for the field",
    )
