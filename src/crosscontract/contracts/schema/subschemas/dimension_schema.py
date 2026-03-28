from typing import Literal

from pydantic import Field

from ..schema import TableSchema


class DimensionSchema(TableSchema):
    """
    A specialized schema for dimension tables in the CrossContract system.

    This schema extends the base `TableSchema` by adding specific constraints
    and conventions for dimension tables, which are typically used for
    categorization and filtering in data models.
    """

    # todo add dimension-specific fields or constraints
    table_type: Literal["Dimension"] = Field(
        default="Dimension",
        description="Type of the table determines the structure of the schema.",
        exclude=True,
        repr=False,
    )
