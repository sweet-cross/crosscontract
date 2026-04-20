from typing import Literal

from pydantic import Field

from ..schema import TableSchema


class ValueVariableSchema(TableSchema):
    """
    A specialized schema for value variable tables in the CrossContract system.

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
