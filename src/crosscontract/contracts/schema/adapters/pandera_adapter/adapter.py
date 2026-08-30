from copy import deepcopy
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:  # pragma: no cover
    from crosscontract.contracts.schema import TableSchema

import pandera.pandas as pa

from crosscontract.contracts.schema.adapters.abstract_adapter import AbstractAdapter
from crosscontract.contracts.schema.validation.checks import (
    IsSubsetOf,
    IsValidCrossDimension,
    IsValidPrimaryKey,
)

from .field_convertors import get_field_converter


def convert_schema_to_pandera(schema: "TableSchema") -> pa.DataFrameSchema:
    """Convert the DataContract to a Pandera DataFrameSchema.

    Args:
        schema (TableSchema): The Schema instance to convert.

    Returns:
        pa.DataFrameSchema: A Pandera DataFrameSchema representing the schema of the
            data described by the Schema.
    """
    return PanderaAdapter.convert_schema(schema)


class PanderaAdapter(AbstractAdapter):
    def create_base_schema(self) -> pa.DataFrameSchema:
        """Create the base Pandera schema with all columns and
        their column level checks.

        Returns:
            pa.DataFrameSchema: The base Pandera DataFrameSchema.
        """
        columns: dict[str, pa.Column] = {
            field.name: get_field_converter(field).convert()
            for field in self.schema.field_iterator()
        }
        pandera_schema = pa.DataFrameSchema(
            columns=columns,
            index=None,  # Currently we do not support index columns
            coerce=True,  # Useful for CSVs (str -> int)
            strict=True,  # Fails if DataFrame contains columns not in Schema
        )
        return pandera_schema

    def add_internal_checks(
        self, pandera_schema: pa.DataFrameSchema
    ) -> pa.DataFrameSchema:
        """Add internal checks to the given Pandera schema.

        Args:
            pandera_schema (pa.DataFrameSchema): The base Pandera schema.

        Returns:
            pa.DataFrameSchema: The Pandera schema with internal checks added.
        """
        new_schema = deepcopy(pandera_schema)
        # add the additional internal reference checks
        checks: list[pa.Check] = []
        if self.schema.primaryKey:
            checks.extend(
                IsValidPrimaryKey(
                    columns=self.schema.primaryKey.fields,
                    label="Internal PrimaryKey Check",
                )
            )
        if self.schema.foreignKeys:
            for fk in self.schema.foreignKeys:
                if fk.reference.resource is None:  # is a self-reference
                    checks.extend(
                        IsSubsetOf(
                            columns=fk.fields,
                            within=fk.reference.fields,
                            label="Internal ForeignKey Check",
                        )
                    )
        if self.schema.table_type == "Dimension":
            checks.extend(IsValidCrossDimension(label="CrossDimension Check"))

        new_schema.checks = new_schema.checks = (new_schema.checks or []) + checks
        return new_schema

    def convert(self, schema: "TableSchema") -> pa.DataFrameSchema:
        """Convert the given TableSchema to a Pandera DataFrameSchema."""
        pandera_schema = self.create_base_schema()
        pandera_schema = self.add_internal_checks(pandera_schema)
        return pandera_schema
