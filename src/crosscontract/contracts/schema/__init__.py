"""The schema is at the core of a contract, defining the structure and types of
data it holds. Schemas ensure data integrity and consistency across different systems
and applications. Schemas are based on Fritionless Schema
standard (https://frictionlessdata.io/docs/specs/schema/).

A schema consists of a collection of fields, each representing a specific data
type and its associated constraints. The schema defines how data should be
validated in the context of a contract.

To make schemas operational, there are methods to convert schema definitions into
Pydantic or Pandera models for data validation and manipulation.

The adapters themselves are not part of this surface: only the
`convert_schema_to_pydantic` convenience is re-exported here. The pandera path has
no such function — `TableSchema.to_pandera_schema()` and
`TableSchema.validate_dataframe()` are its public entry points, and
`PanderaAdapter` is reached through them.
"""

from crosscontract.exceptions import SchemaValidationError

from .adapters import convert_schema_to_pydantic
from .field_descriptors import FieldDescriptors
from .fields import (
    BaseField,
    DateTimeField,
    IntegerField,
    ListField,
    NumberField,
    StringField,
)
from .reference import ForeignKeys, PrimaryKey
from .schema import TableSchema
from .subschemas import DimensionSchema, FlexibleDimensionSchema, ValueVariableSchema

__all__ = [
    "TableSchema",
    "convert_schema_to_pydantic",
    "SchemaValidationError",
    "PrimaryKey",
    "ForeignKeys",
    "FieldDescriptors",
    "StringField",
    "IntegerField",
    "NumberField",
    "DateTimeField",
    "ListField",
    "BaseField",
    "DimensionSchema",
    "ValueVariableSchema",
    "FlexibleDimensionSchema",
]
