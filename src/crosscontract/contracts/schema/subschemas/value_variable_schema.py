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
    table_type: Literal["ValueVariable"] = Field(
        default="ValueVariable",
        description="Type of the table determines the structure of the schema.",
        exclude=True,
        repr=False,
    )
