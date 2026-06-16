"""Pydantic models for the Frictionless Table Schema standard.

Internal: received by consumers via released artifacts, but not re-exported from
the top-level `crosscontract` package.
"""

from .descriptors import DataPackage, DataResource
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
from .metadata import (
    FRICTIONLESS_NAME_PATTERN,
    BaseMetaData,
    Contributor,
    FileMetaData,
    License,
    PackageMetaData,
    ResourceMetaData,
    Source,
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
    # descriptors
    "DataResource",
    "DataPackage",
    # metadata building blocks
    "FRICTIONLESS_NAME_PATTERN",
    "BaseMetaData",
    "FileMetaData",
    "ResourceMetaData",
    "PackageMetaData",
    "Source",
    "License",
    "Contributor",
]
