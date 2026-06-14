"""Frictionless Table Schema model.

A faithful, *permissive* pydantic representation of the Frictionless Table Schema
standard: a collection of typed `fields` plus `primaryKey`, `foreignKeys`, and
`missingValues`. All models allow extra keys so the standard's extensibility rides
through losslessly.

Note: `TableSchema` here is the *standard* schema and shares its bare name with the
stricter contract schema in `crosscontract.contracts.schema.schema`. Callers
disambiguate by module (e.g. import the package as `frictionless`).
"""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .fields import (
    AnyField,
    ArrayField,
    BooleanField,
    DateTimeField,
    IntegerField,
    NumberField,
    StringField,
)

_MODEL_CONFIG = ConfigDict(extra="allow", str_strip_whitespace=True)

FieldUnion = Annotated[
    StringField
    | IntegerField
    | NumberField
    | DateTimeField
    | ArrayField
    | BooleanField
    | AnyField,
    Field(discriminator="type"),
]


class Reference(BaseModel):
    """The `reference` object of a Frictionless foreign key."""

    model_config = _MODEL_CONFIG

    resource: str = Field(
        default="",
        description=(
            "The name of the resource the foreign key references. An empty string "
            "references the current resource."
        ),
    )
    fields: list[str] = Field(
        description="The referenced field name(s).",
        min_length=1,
    )

    @field_validator("fields", mode="before")
    @classmethod
    def _to_list(cls, value: str | list[str]) -> list[str] | str:
        """Normalize a single field name to a one-element list.

        The standard allows `fields` to be a string or an array of strings.

        Returns:
            list[str] | str: A list when a bare string was given, else `value`
            unchanged (let validation handle non-string/list inputs).
        """
        if isinstance(value, str):
            return [value]
        return value


class ForeignKey(BaseModel):
    """A Frictionless foreign key: local field(s) and their reference."""

    model_config = _MODEL_CONFIG

    fields: list[str] = Field(
        description="The local field name(s) that make up the foreign key.",
        min_length=1,
    )
    reference: Reference = Field(
        description="The reference the foreign key points to.",
    )

    @field_validator("fields", mode="before")
    @classmethod
    def _to_list(cls, value: str | list[str]) -> list[str] | str:
        """Normalize a single field name to a one-element list.

        Returns:
            list[str] | str: A list when a bare string was given, else `value`
            unchanged.
        """
        if isinstance(value, str):
            return [value]
        return value


class TableSchema(BaseModel):
    """A Frictionless Table Schema.

    An `array` of typed field objects together with the optional `primaryKey`,
    `foreignKeys`, and `missingValues`. A typeless field defaults to `string`, per
    the standard.
    """

    model_config = _MODEL_CONFIG

    fields: list[FieldUnion] = Field(
        description="An `array` of Table Schema field objects.",
        min_length=1,
    )
    primaryKey: list[str] = Field(
        default_factory=list,
        description=(
            "A field name or an array of field names whose values uniquely "
            "identify each row in the table."
        ),
    )
    foreignKeys: list[ForeignKey] = Field(
        default_factory=list,
        description="The foreign key definitions relating this table to others.",
    )
    missingValues: list[str] = Field(
        default_factory=lambda: [""],
        description=(
            "Values that, when encountered in the source, are considered as "
            "`null` / 'not present' / 'blank'."
        ),
    )

    @field_validator("primaryKey", mode="before")
    @classmethod
    def _primary_key_to_list(cls, value: str | list[str]) -> list[str] | str:
        """Normalize a single primary-key field name to a one-element list.

        The standard allows `primaryKey` to be a string or an array of strings.

        Returns:
            list[str] | str: A list when a bare string was given, else `value`
            unchanged.
        """
        if isinstance(value, str):
            return [value]
        return value

    @model_validator(mode="before")
    @classmethod
    def _default_field_type(cls, data: Any) -> Any:
        """Inject `type="string"` into typeless field definitions.

        The Frictionless standard makes `type` optional and defaults a typeless
        field to `string`. The discriminated `FieldUnion` requires the discriminator
        to be present, so this fills it in before discrimination. Field entries that
        are already model instances are left untouched.

        Returns:
            Any: The input with each typeless field dict given an explicit
            `type` of `string`.
        """
        if isinstance(data, dict):
            fields = data.get("fields")
            if isinstance(fields, list):
                data["fields"] = [
                    {**field, "type": field.get("type", "string")}
                    if isinstance(field, dict)
                    else field
                    for field in fields
                ]
        return data
