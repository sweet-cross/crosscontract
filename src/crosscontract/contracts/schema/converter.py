"""Converters take a schema as input and convert it into to different formats
such as Pydantic models, Pandera DataFrames, or SQLAlchemy columns."""

from typing import Any

import pandera.pandas as pa
from pydantic import BaseModel, Field
from pydantic import create_model as create_pydantic_model
from sqlalchemy import Column, Integer, MetaData, Table

from .schema import TableSchema


def convert_schema_to_pydantic(
    schema: TableSchema,
    name: str = "ConvertedModel",
    base_class: type[BaseModel] = BaseModel,
) -> type[BaseModel]:
    """Convert the schema to a Pydantic model."""
    field_definitions: dict[str, Any] = {}

    for field in schema:
        # Extract the type
        field_type = field.get_type_hint()

        # Extract the field args
        field_kwargs = field.get_pydantic_field_kwargs()
        field_definitions[field.name] = (field_type, Field(**field_kwargs))

    return create_pydantic_model(  # type: ignore[call-overload]
        name,
        __base__=base_class,
        **field_definitions,
    )


def convert_schema_to_pandera(
    schema: TableSchema,
    name: str = "ConvertedSchema",
) -> pa.DataFrameSchema:
    """Convert the DataContract to a Pandera DataFrameSchema.

    Args:
        schema (Schema): The Schema instance to convert.
        name (str): The name of the resulting DataFrameSchema.

    Returns:
        pa.DataFrameSchema: A Pandera DataFrameSchema representing the schema of the
            data described by the Schema.
    """

    columns: dict[str, pa.Column] = {
        field.name: pa.Column(**field.get_pandera_kwargs()) for field in schema
    }

    return pa.DataFrameSchema(
        columns=columns,
        index=None,  # Currently we do not support index columns
        name=name,
        coerce=True,  # Useful for CSVs (str -> int)
        strict=True,  # Fails if DataFrame contains columns not in Schema
    )


def convert_schema_to_sqlalchemy(
    schema: TableSchema,
    metadata: MetaData,
    table_name: str,
) -> Table:
    """Convert the DataContract to a SQLAlchemy table.

    Args:
        schema (Schema): The Schema instance to convert.
        metadata (MetaData): SQLAlchemy MetaData instance to use for the table.
        table_name (str): The name of the table to create.

    Returns:
        Table: The SQLAlchemy table representation of the DataContract.
    """
    # always add a primary key field
    if "_id" in schema.field_names:
        raise ValueError(
            "Schema cannot have a field named '_id' as it uses it as primary key."
        )
    id_column = Column("_id", Integer, primary_key=True)
    columns = [id_column] + [field.to_sqlalchemy_column() for field in schema]
    return Table(table_name, metadata, *columns, extend_existing=True)
