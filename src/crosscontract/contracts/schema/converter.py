"""Converters take a schema as input and convert it into to different formats
such as Pydantic models, Pandera DataFrames, or SQLAlchemy columns."""

import pandera.pandas as pa
from sqlalchemy import Column, Integer, MetaData, Table

from .schema import TableSchema


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
        field.name: pa.Column(**field.get_pandera_kwargs())
        for field in schema.field_iterator()
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
    columns = [id_column] + [
        field.to_sqlalchemy_column() for field in schema.field_iterator()
    ]
    return Table(table_name, metadata, *columns, extend_existing=True)
