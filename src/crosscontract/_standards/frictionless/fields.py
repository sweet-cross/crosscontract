"""Frictionless Table Schema field models.

A faithful, *permissive* pydantic representation of the field objects defined by
the Frictionless Table Schema standard. Unlike the contract fields in
`crosscontract.contracts.schema.fields`, these models impose no domain logic and
allow extra keys (`extra="allow"`) so the standard's extensibility — and the
contract's `fieldDescriptors` and any custom properties — ride through losslessly.

This first pass covers `string`, `integer`, `number`, `datetime`, `array`,
`boolean`, and `any`. The remaining Frictionless types are deferred.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

_MODEL_CONFIG = ConfigDict(extra="allow", str_strip_whitespace=True)


class BaseConstraint(BaseModel):
    """Constraints shared by every field type.

    See the `constraints` object of the Frictionless field definition.
    """

    model_config = _MODEL_CONFIG

    required: bool = Field(
        default=False,
        description="Indicates whether a property must have a value for each instance.",
    )
    unique: bool = Field(
        default=False,
        description="When `true`, each value for the property `MUST` be unique.",
    )


class StringConstraint(BaseConstraint):
    """Constraints for `string` fields."""

    pattern: str | None = Field(
        default=None,
        description=(
            "A regular expression pattern to test each value of the property "
            "against, where a truthy response indicates validity."
        ),
    )
    enum: list[Any] | None = Field(
        default=None,
        min_length=1,
        description=(
            "The value of the field `MUST` exactly match one of the enum values."
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


class NumericConstraint(BaseConstraint):
    """Constraints for `integer` and `number` fields."""

    minimum: float | None = Field(
        default=None,
        description="Specifies a minimum value for a field.",
    )
    maximum: float | None = Field(
        default=None,
        description="Specifies a maximum value for a field.",
    )
    enum: list[Any] | None = Field(
        default=None,
        min_length=1,
        description=(
            "The value of the field `MUST` exactly match one of the enum values."
        ),
    )


class DateTimeConstraint(BaseConstraint):
    """Constraints for `datetime` fields."""

    minimum: str | None = Field(
        default=None,
        description="Specifies a minimum value for a field.",
    )
    maximum: str | None = Field(
        default=None,
        description="Specifies a maximum value for a field.",
    )
    enum: list[Any] | None = Field(
        default=None,
        min_length=1,
        description=(
            "The value of the field `MUST` exactly match one of the enum values."
        ),
    )


class ArrayConstraint(BaseConstraint):
    """Constraints for `array` fields."""

    enum: list[Any] | None = Field(
        default=None,
        min_length=1,
        description=(
            "The value of the field `MUST` exactly match one of the enum values."
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


class BooleanConstraint(BaseConstraint):
    """Constraints for `boolean` fields."""

    enum: list[Any] | None = Field(
        default=None,
        min_length=1,
        description=(
            "The value of the field `MUST` exactly match one of the enum values."
        ),
    )


class AnyConstraint(BaseConstraint):
    """Constraints for `any` fields."""

    enum: list[Any] | None = Field(
        default=None,
        min_length=1,
        description=(
            "The value of the field `MUST` exactly match one of the enum values."
        ),
    )


class BaseField(BaseModel):
    """Properties shared by every Frictionless field.

    Field `name` is an arbitrary, required string — the Frictionless standard
    places no pattern on it (unlike the CROSS contract fields).
    """

    model_config = _MODEL_CONFIG

    name: str = Field(
        description="A name for this field.",
    )
    title: str | None = Field(
        default=None,
        description="A human-readable title for the field.",
    )
    description: str | None = Field(
        default=None,
        description="A human-readable description of the field.",
    )
    example: Any | None = Field(
        default=None,
        description="An example value for the field.",
    )
    rdfType: str | None = Field(
        default=None,
        description="The RDF type for this field.",
    )
    format: str = Field(
        default="default",
        description=(
            "The format keyword options for the field type. Free-form per the "
            "standard (e.g. `datetime` accepts strptime patterns)."
        ),
    )


class StringField(BaseField):
    """A `string` field.

    Standard `format` values: `default`, `email`, `uri`, `binary`, `uuid`.
    """

    type: Literal["string"] = Field(
        default="string",
        description="The type keyword, which `MUST` be a value of `string`.",
    )
    constraints: StringConstraint = Field(
        default_factory=StringConstraint,
        description="Constraints for the `string` field.",
    )


class IntegerField(BaseField):
    """An `integer` field."""

    type: Literal["integer"] = Field(
        default="integer",
        description="The type keyword, which `MUST` be a value of `integer`.",
    )
    bareNumber: bool = Field(
        default=True,
        description=(
            "If `false`, the contents of the field may contain leading and/or "
            "trailing non-numeric characters."
        ),
    )
    constraints: NumericConstraint = Field(
        default_factory=NumericConstraint,
        description="Constraints for the `integer` field.",
    )


class NumberField(BaseField):
    """A `number` field."""

    type: Literal["number"] = Field(
        default="number",
        description="The type keyword, which `MUST` be a value of `number`.",
    )
    bareNumber: bool = Field(
        default=True,
        description=(
            "If `false`, the contents of the field may contain leading and/or "
            "trailing non-numeric characters."
        ),
    )
    decimalChar: str = Field(
        default=".",
        description="A string whose value is used to represent a decimal point.",
    )
    groupChar: str | None = Field(
        default=None,
        description="A string whose value is used to group digits.",
    )
    constraints: NumericConstraint = Field(
        default_factory=NumericConstraint,
        description="Constraints for the `number` field.",
    )


class DateTimeField(BaseField):
    """A `datetime` field.

    `format` is free-form: `default`, `any`, or a strptime pattern.
    """

    type: Literal["datetime"] = Field(
        default="datetime",
        description="The type keyword, which `MUST` be a value of `datetime`.",
    )
    constraints: DateTimeConstraint = Field(
        default_factory=DateTimeConstraint,
        description="Constraints for the `datetime` field.",
    )


class ArrayField(BaseField):
    """An `array` field."""

    type: Literal["array"] = Field(
        default="array",
        description="The type keyword, which `MUST` be a value of `array`.",
    )
    constraints: ArrayConstraint = Field(
        default_factory=ArrayConstraint,
        description="Constraints for the `array` field.",
    )


class BooleanField(BaseField):
    """A `boolean` field."""

    type: Literal["boolean"] = Field(
        default="boolean",
        description="The type keyword, which `MUST` be a value of `boolean`.",
    )
    trueValues: list[str] = Field(
        default_factory=lambda: ["true", "True", "TRUE", "1"],
        description="Values to read as `true`.",
    )
    falseValues: list[str] = Field(
        default_factory=lambda: ["false", "False", "FALSE", "0"],
        description="Values to read as `false`.",
    )
    constraints: BooleanConstraint = Field(
        default_factory=BooleanConstraint,
        description="Constraints for the `boolean` field.",
    )


class AnyField(BaseField):
    """An `any` field — accepts any value, no casting."""

    type: Literal["any"] = Field(
        default="any",
        description="The type keyword, which `MUST` be a value of `any`.",
    )
    constraints: AnyConstraint = Field(
        default_factory=AnyConstraint,
        description="Constraints for the `any` field.",
    )
