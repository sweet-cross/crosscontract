from typing import Any, Literal

import pandera.pandas as pa
from pydantic import Field
from sqlalchemy import ARRAY, Boolean, Column, Float, Integer, String

from .base import BaseConstraint, BaseField

MAP_ITEM_TYPES_PYTHON: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}

MAP_ITEM_TYPES_SQL: dict[str, type] = {
    "string": String,
    "integer": Integer,
    "number": Float,
    "boolean": Boolean,
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

    def get_pydantic_field_kwargs(self) -> dict[str, Any]:
        """Returns the pydantic field kwargs for the array constraint."""
        kwargs = super().get_pydantic_field_kwargs()

        # Handle minLength and maxLength constraints
        if self.minLength is not None:
            kwargs["min_length"] = self.minLength
        if self.maxLength is not None:
            kwargs["max_length"] = self.maxLength

        return kwargs

    def get_pandera_kwargs(self):
        kwargs = super().get_pandera_kwargs()
        # Handle minLength and maxLength constraints
        if self.minLength is not None:
            min_len = self.minLength
            kwargs["checks"].append(
                pa.Check(lambda s: s.apply(lambda lst: len(lst) >= min_len))
            )
        if self.maxLength is not None:
            max_len = self.maxLength
            kwargs["checks"].append(
                pa.Check(lambda s: s.apply(lambda lst: len(lst) <= max_len))
            )
        return kwargs


class ListField(BaseField):
    """ListFields store items into a list-like structure."""

    type: Literal["list"] = Field(
        default="list",
        description="The type of the field, which is 'list' for this class.",
    )

    itemType: Literal["string", "integer", "number", "boolean"] = Field(
        default="string", description="The type of items in the array"
    )

    constraints: ListConstraint = Field(
        default_factory=lambda: ListConstraint(),
        description="Constraints for the list field",
    )

    @property
    def python_type(self) -> type:  # type: ignore
        return list[MAP_ITEM_TYPES_PYTHON[self.itemType]]  # type: ignore

    def to_sqlalchemy_column(self):
        return Column(
            self.name,
            ARRAY(MAP_ITEM_TYPES_SQL[self.itemType]),
            nullable=not self.constraints.required,
        )
