from typing import Literal

from pydantic import Field, model_validator

from ..schema import TableSchema


class ValueVariableSchema(TableSchema):
    """
    A specialized schema for value variable tables in the CrossContract system.

    A ValueVariable is defined as one or more numeric measurements together with
    a key that uniquely identifies the rows. Thus, each column must be either part
    of the key or a numeric measurement. Moreover, we do not allow for measurements
    without an associated key column.

    This schema extends the base `TableSchema` by adding specific constraints
    and conventions for value variable tables, which are typically used for
    categorization and filtering in data models.
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
    def _check_non_primary_key_measurements_are_numeric(self, values):
        """Check that all non-primary key columns are numeric measurements."""
        if not self.primaryKey:
            raise ValueError("ValueVariable tables must have a primary key.")

        primary_key_columns = set(self.primaryKey.root)
        wrong_fields = []
        for field in self.field_iterator():
            if field.name in primary_key_columns:
                continue
            if field.type not in ["integer", "number"]:
                wrong_fields.append(field.name)
        if wrong_fields:
            raise ValueError(
                f"Non-primary key columns '{', '.join(wrong_fields)}' must be numeric"
                "measurements."
            )
        return values
