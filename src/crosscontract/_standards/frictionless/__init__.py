"""Pydantic models for the Frictionless Table Schema standard.

Internal: received by consumers via released artifacts, but not re-exported from
the top-level `crosscontract` package.
"""

from .fields import (
    AnyField,
    ArrayField,
    BaseConstraint,
    BaseField,
    BooleanField,
    DateTimeField,
    IntegerField,
    NumberField,
    StringField,
)
from .table_schema import FieldUnion, ForeignKey, Reference, TableSchema

__all__ = [
    # fields
    "BaseField",
    "BaseConstraint",
    "StringField",
    "IntegerField",
    "NumberField",
    "DateTimeField",
    "ArrayField",
    "BooleanField",
    "AnyField",
    # table_schema
    "TableSchema",
    "FieldUnion",
    "ForeignKey",
    "Reference",
]
