from abc import ABC, abstractmethod
from typing import Any, Literal

import pandera.pandas as pa
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column

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

    @abstractmethod
    def get_pydantic_field_kwargs(self) -> dict[str, Any]:
        """Returns the pydantic field kwargs for the constraint."""
        kwargs: dict[str, Any] = {}

        # Handle required constraint
        if self.required is False:
            kwargs["default"] = None  # Optional field

        # Handle unique constraint
        if self.unique is True:
            kwargs["json_schema_extra"] = kwargs.get("json_schema_extra", {})
            kwargs["json_schema_extra"]["unique"] = True

        # Handle enum constraint
        enum_constraint = getattr(self, "enum", None)
        if enum_constraint is not None:
            kwargs["json_schema_extra"] = kwargs.get("json_schema_extra", {})
            kwargs["json_schema_extra"] = {"enum": list(enum_constraint)}

        return kwargs

    @abstractmethod
    def get_pandera_kwargs(self) -> dict[str, Any]:
        """Returns the keyword arguments to create a pandera Column for this
        constraint."""
        kwargs: dict[str, Any] = {}
        kwargs["checks"] = []

        kwargs["required"] = self.required if self.required is not None else False

        # Handle required constraint
        if not kwargs["required"]:
            kwargs["nullable"] = True

        # Handle unique constraint
        if self.unique is True:
            kwargs["unique"] = True

        # Handle enum constraint
        enum_constraint = getattr(self, "enum", None)
        if enum_constraint is not None:
            kwargs["checks"].append(pa.Check.isin(enum_constraint))

        return kwargs


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

    @property
    @abstractmethod
    def python_type(self) -> type:
        """Returns the Python type of the field. This is used in the
        derivation of the pydantic model"""
        raise NotImplementedError("Subclasses must implement this method.")

    @property
    def pandera_type(self) -> type | str:
        """Returns the Pandera type of the field. This is used in the
        derivation of the Pandera schema."""
        return self.python_type

    def get_type_hint(self) -> Any:
        """Returns the type hint for the field based on the constraints."""
        enum_constraint = getattr(self.constraints, "enum", None)
        if enum_constraint is not None:
            return (
                Literal[*enum_constraint]
                if self.constraints.required
                else Literal[*enum_constraint] | None
            )
        else:
            return (
                self.python_type
                if self.constraints.required
                else self.python_type | None
            )

    def get_pydantic_field_kwargs(self) -> dict[str, Any]:
        """Returns the pydantic field kwargs for the field."""
        kwargs = {
            "title": self.title,
            "description": self.description,
            "json_schema_extra": {
                "name": self.name,
            },
        }
        # get the additional kwargs from the constraints
        kwargs.update(self.constraints.get_pydantic_field_kwargs())

        return kwargs

    def get_pandera_kwargs(self) -> dict[str, Any]:
        """Returns the keyword arguments to create a pandera Column for this
        field."""
        kwargs = {
            "name": self.name,
            "dtype": self.pandera_type,
            "title": self.title,
            "description": self.description,
            # "dtype": map_pandera_type_hints.get(self.get_type_hint()),
        }

        # get the additional kwargs from the constraints
        kwargs.update(self.constraints.get_pandera_kwargs())

        return kwargs

    @abstractmethod
    def to_sqlalchemy_column(self) -> Column:
        """Returns the SQLAlchemy Column for the field."""
        raise NotImplementedError("Subclasses must implement this method.")
