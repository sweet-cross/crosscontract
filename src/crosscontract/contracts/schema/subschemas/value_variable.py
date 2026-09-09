from typing import Literal, Self

from pydantic import Field, model_validator

from ..schema import TableSchema


class ValueVariableSchema(TableSchema):
    """
    A specialized schema for value variable tables in the CrossContract system.

    A value variable is a primary key that identifies the row plus one or more
    numeric measures, so every field is one or the other:

    - the schema must declare a non-empty `primaryKey`;
    - at least one field must lie outside that key;
    - every field outside the key must be of type `integer` or `number`.

    A non-numeric attribute therefore has to be part of the row's identity, or it
    does not belong in the contract at all.

    Key columns are not required to reference a dimension, so being in the
    primary key does not imply being an axis to aggregate over.
    """

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
        """Enforce that the schema is a primary key plus numeric measures.

        Three rules, checked in order:

        1. The schema declares a non-empty `primaryKey`.
        2. At least one field lies outside that key.
        3. Every field outside the key is of type `integer` or `number`.

        Returns:
            Self: The validated schema.

        Raises:
            ValueError: If the primary key is missing, if no field lies outside
                it, or if a field outside it is not numeric.
        """
        if not self.primaryKey:
            raise ValueError("ValueVariable tables must have a primary key.")

        primary_key_columns = set(self.primaryKey.fields)
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
                f"Non-primary key columns '{', '.join(wrong_fields)}' must be "
                "numeric measurements."
            )
        return self
