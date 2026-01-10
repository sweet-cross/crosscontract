"""The schema is at the core of a contract, defining the structure and types of
data it holds. Schemas ensure data integrity and consistency across different systems
and applications. Schemas are based on Fritionless Schema
standard (https://frictionlessdata.io/docs/specs/schema/).

A schema consists of a collection of fields, each representing a specific data
type and its associated constraints. The schema defines how data should be
validated in the context of a contract.

To make schemas operational, there are methods to convert schema definitions into
Pydantic or Pandera models for data validation and manipulation, as well as into
SQLAlchemy columns, enabling seamless integration with databases.
"""

from .converter import (
    convert_schema_to_pandera,
    convert_schema_to_pydantic,
    convert_schema_to_sqlalchemy,
)
from .exceptions import SchemaValidationError
from .schema import TableSchema

__all__ = [
    "TableSchema",
    "convert_schema_to_pydantic",
    "convert_schema_to_pandera",
    "convert_schema_to_sqlalchemy",
    "SchemaValidationError",
]
