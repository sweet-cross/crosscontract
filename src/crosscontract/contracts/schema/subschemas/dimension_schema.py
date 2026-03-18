from typing import Literal

from ..schema import TableSchema


class DimensionSchema(TableSchema):
    """
    A specialized schema for dimension tables in the CrossContract system.

    This schema extends the base `TableSchema` by adding specific constraints
    and conventions for dimension tables, which are typically used for
    categorization and filtering in data models.
    """

    # todo add dimension-specific fields or constraints
    contract_type: Literal["Dimension"]
