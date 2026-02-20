from typing import Literal

from pydantic import Field

from .base import BaseConstraint, BaseField

MAP_ITEM_TYPES_PYTHON: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}


class ListConstraint(BaseConstraint):
    """ListConstraint defines constraints for a list of items. The items must
    be of the same type. The default assumed type is "string"."""

    minLength: int | None = Field(
        default=None,
        description=(
            "Minimum length of the array, i.e., the minimum number of elements"
            " in the array"
        ),
        ge=0,  # Ensure minLength is non-negative
    )
    maxLength: int | None = Field(
        default=None,
        description=(
            "Maximum length of the array, i.e., the maximum number of elements"
            " in the array"
        ),
        ge=0,  # Ensure maxLength is non-negative
    )


class ListField(BaseField):
    """ListFields store items into a list-like structure. All items in the list
    must be of the same type. List fields can have constraints on the length of
    the list.
    """

    type: Literal["list"] = Field(
        default="list",
        description="The type of the field, which is 'list' for this class.",
    )

    itemType: Literal["string", "integer", "number", "boolean"] = Field(
        default="string", description="The type of items in the array"
    )

    constraints: ListConstraint = Field(
        default_factory=ListConstraint,
        description="Constraints for the list field",
    )
