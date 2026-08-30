"""Adapters take a schema and convert it to a different format.
For example, the PydanticAdapter converts a schema into a corresponding pydantic
model that allows to validate a single row of data against the schema. Likewise,
the PanderaAdapter converts a schema into a corresponding pandera schema that allows
to validate a dataframe against the schema."""

from .pandera_pandas import PanderaAdapter
from .pydantic_adapter import PydanticAdapter, convert_schema_to_pydantic
from .sqlalchemy_adapter import SQLAlchemyPostgresAdapter, convert_schema_to_sqlalchemy

__all__ = [
    "PydanticAdapter",
    "convert_schema_to_pydantic",
    "SQLAlchemyPostgresAdapter",
    "convert_schema_to_sqlalchemy",
    "PanderaAdapter",
]
