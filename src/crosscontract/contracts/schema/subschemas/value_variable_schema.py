from typing import Literal

from ..schema import TableSchema


class ValueVariableSchema(TableSchema):
    """
    A specialized schema for value variable tables in the CrossContract system.

    This schema extends the base `TableSchema` by adding specific constraints
    and conventions for value variable tables, which are typically used for
    categorization and filtering in data models.
    """

    # todo add value variable-specific fields or constraints
    contract_type: Literal["ValueVariable"]
