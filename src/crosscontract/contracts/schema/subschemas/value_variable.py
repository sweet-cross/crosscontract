from typing import Literal, Self

from pydantic import Field, model_validator

from ..schema import TableSchema


class ValueVariableSchema(TableSchema):
    """
    A specialized schema for value variable tables in the CrossContract system.

    A value variable is a primary key that identifies the row plus one or more
    numeric measures, so every field is one or the other:

    - the schema must declare a non-empty `primaryKey`;
    - every field outside that key must be of type `integer` or `number`.

    A non-numeric attribute therefore has to be part of the row's identity — the
    same quantity delivered in two units is two rows, so `unit` belongs in the
    key — or it does not belong in the contract at all.

    Key columns are not required to reference a dimension, so being in the
    primary key does not imply being an axis: summing across a qualifier such as
    `unit` is meaningless.
    """

    # todo add value variable-specific fields or constraints
    # ignore type error as we want to enforce the table_type for this schema
    # for the pydantic discriminator to work correctly
    table_type: Literal["ValueVariable"] = Field(  # type: ignore[assignment]
        default="ValueVariable",
        description="Type of the table determines the structure of the schema.",
        exclude=True,
        repr=False,
    )

    @model_validator(mode="after")
    def _check_is_value_variable(self) -> Self:
        """Check that the schema conforms to the value variable constraints. That
        includes three tests:
        1. The schema must have a non-empty primary key.
        2. Every field outside the primary key must be of type `integer` or `number`.
        3. The schema must have at least one non-numeric attribute in the primary key.
        """
        if not self.primaryKey:
            raise ValueError("ValueVariable tables must have a primary key.")

        primary_key_columns = set(self.primaryKey.root)
        non_key_fields = {
            field.name: field.type
            for field in self.field_iterator()
            if field.name not in primary_key_columns
        }
        if len(non_key_fields) == 0:
            raise ValueError(
                "ValueVariable tables must have at least one non-primary key field."
            )

        wrong_fields = []
        for field, field_type in non_key_fields.items():
            if field_type not in ["integer", "number"]:
                wrong_fields.append(field)
        if wrong_fields:
            raise ValueError(
                f"Non-primary key columns '{', '.join(wrong_fields)}' must be numeric"
                "measurements."
            )
        return self
