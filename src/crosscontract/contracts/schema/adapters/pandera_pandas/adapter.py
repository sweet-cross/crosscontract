from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from crosscontract.contracts.schema import TableSchema

import pandera.pandas as pa

from crosscontract.contracts.schema.adapters.abstract_adapter import AbstractAdapter
from crosscontract.contracts.schema.validation.checks import (
    BaseCheck,
    HasNoDescendantInGroup,
    IsSubsetOf,
    IsValidCrossDimension,
    IsValidPrimaryKey,
)

from .field_convertors import get_field_converter


class PanderaAdapter(AbstractAdapter):
    """Adapter that converts a schema into a corresponding pandera schema that
    allows to validate a Pandas DataFrame against the schema.
    """

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

    def _derive_checks(
        self,
        primary_key_values: list[tuple[Any, ...]] | None = None,
        foreign_key_values: dict[tuple[str, ...], list[tuple[Any, ...]]] | None = None,
        dimension_hierarchies: dict[str, dict[str, str | None]] | None = None,
    ) -> list[BaseCheck]:
        """Derive the checks this schema requires of a DataFrame.

        One check per schema construct: the primary key, each foreign key, and
        the hierarchy of a `Dimension`. Existing values are optional and widen
        what a check compares against, never which checks exist — so a caller can
        inform a check but cannot drop one.

        A foreign key referring to another contract is the one construct that may
        yield no check: without the referenced values there is nothing to compare
        against, and it is left unchecked. A self-referencing key always yields
        one, because the DataFrame's own rows are the referenced values.

        Args:
            primary_key_values (list[tuple[Any, ...]] | None, optional): The
                primary keys already stored for this contract. `None` leaves the
                primary key unchecked; an empty list checks it within the
                DataFrame alone.
                Defaults to `None`.
            foreign_key_values (dict[tuple[str, ...], list[tuple[Any, ...]]]
                | None, optional): The referenced values already stored, keyed by
                the tuple of referring fields. `None` leaves the foreign keys
                unchecked. An empty dict checks self-referencing keys against the
                DataFrame's own rows; an external reference is checked only when
                its values are given.
                Defaults to `None`.
            dimension_hierarchies (dict[str, dict[str, str | None]] | None, optional):
                The hierarchy of each referenced dimension, keyed by the column
                that references it and mapping a member to its parent. Supplying
                one checks that no group reports a member alongside one of its
                descendants; `None` leaves the hierarchies unchecked. A group is
                the schema's primary key minus the column being judged, so a
                schema declaring no primary key puts every row in one group.
                Defaults to `None`.

        Returns:
            list[BaseCheck]: The checks to run against the data.

        Raises:
            ValueError: If a column in `dimension_hierarchies` is not a field of
                the schema.
        """
        checks: list[BaseCheck] = []

        if primary_key_values is not None and self.schema.primaryKey:
            checks.append(
                IsValidPrimaryKey(
                    columns=self.schema.primaryKey.fields,
                    existing=primary_key_values,
                    label="primary key",
                )
            )

        if foreign_key_values is not None and self.schema.foreignKeys:
            for fk in self.schema.foreignKeys:
                # a self-reference takes its valid set from the frame itself
                within = fk.reference.fields if fk.reference.resource is None else None
                allowed = (foreign_key_values or {}).get(tuple(fk.fields))
                if within is None and allowed is None:
                    continue
                checks.append(
                    IsSubsetOf(
                        columns=fk.fields,
                        allowed=allowed or [],
                        within=within,
                        label="foreign key",
                    )
                )

        if self.schema.table_type == "Dimension":
            checks.append(IsValidCrossDimension(label="dimension hierarchy"))

        if dimension_hierarchies is not None:
            wrong_columns = [
                c for c in dimension_hierarchies if c not in self.schema.field_names
            ]
            if wrong_columns:
                raise ValueError(
                    "Dimension hierarchies contain unknown columns: "
                    f"{', '.join(wrong_columns)}"
                )
            for column, parent_map in dimension_hierarchies.items():
                # groups are the set of rows in the primary key excluding the
                # controlled column
                groups = [col for col in self.schema.primaryKey.fields if col != column]
                checks.append(
                    HasNoDescendantInGroup(
                        column=column,
                        group_columns=groups,
                        parent_map=parent_map,
                        label="dimension granularity",
                    )
                )

        return checks

    def convert(
        self,
        primary_key_values: list[tuple[Any, ...]] | None = None,
        foreign_key_values: dict[tuple[str, ...], list[tuple[Any, ...]]] | None = None,
        dimension_hierarchies: dict[str, dict[str, str | None]] | None = None,
    ) -> pa.DataFrameSchema:
        """Convert the TableSchema into a Pandera DataFrameSchema.

        Args:
            primary_key_values (list[tuple[Any, ...]] | None, optional): The
                primary keys already stored for this contract. `None` leaves the
                primary key unchecked; an empty list checks it within the
                DataFrame alone.
                Defaults to `None`.
            foreign_key_values (dict[tuple[str, ...], list[tuple[Any, ...]]] |
                None, optional): The referenced values already stored, keyed by
                the tuple of referring fields. `None` leaves the foreign keys
                unchecked. An empty dict checks self-referencing keys against the
                DataFrame's own rows; an external reference is checked only when
                its values are given.
                Defaults to `None`.
            dimension_hierarchies (dict[str, dict[str, str | None]] | None, optional):
                The hierarchy of each referenced dimension, keyed by the column
                that references it and mapping a member to its parent. Supplying
                one checks that no group reports a member alongside one of its
                descendants; `None` leaves the hierarchies unchecked. A group is
                the schema's primary key minus the column being judged, so a
                schema declaring no primary key puts every row in one group.
                Defaults to `None`.

        Returns:
            pa.DataFrameSchema: The converted Pandera DataFrameSchema, carrying the
                columns of the schema and the checks it requires of its own data.
        """
        pandera_schema = self.create_base_schema()
        checks = self._derive_checks(
            primary_key_values=primary_key_values,
            foreign_key_values=foreign_key_values,
            dimension_hierarchies=dimension_hierarchies,
        )
        pandera_schema.checks = (pandera_schema.checks or []) + [
            pandera_check for check in checks for pandera_check in check.to_pandera()
        ]

        return pandera_schema

    @classmethod
    def convert_schema(
        cls,
        schema: "TableSchema",
        primary_key_values: list[tuple[Any, ...]] | None = None,
        foreign_key_values: dict[tuple[str, ...], list[tuple[Any, ...]]] | None = None,
        dimension_hierarchies: dict[str, dict[str, str | None]] | None = None,
    ) -> pa.DataFrameSchema:
        """Convert a TableSchema without needing to instantiate the adapter.

        Args:
            schema (TableSchema): The TableSchema to convert.
            primary_key_values (list[tuple[Any, ...]] | None, optional): The
                primary keys already stored for this contract. `None` leaves the
                primary key unchecked; an empty list checks it within the
                DataFrame alone.
                Defaults to `None`.
            foreign_key_values (dict[tuple[str, ...], list[tuple[Any, ...]]]
                | None, optional): The referenced values already stored, keyed by
                the tuple of referring fields. `None` leaves the foreign keys
                unchecked. An empty dict checks self-referencing keys against the
                DataFrame's own rows; an external reference is checked only when
                its values are given.
                Defaults to `None`.
            dimension_hierarchies (dict[str, dict[str, str | None]] | None, optional):
                The hierarchy of each referenced dimension, keyed by the column
                that references it and mapping a member to its parent. Supplying
                one checks that no group reports a member alongside one of its
                descendants; `None` leaves the hierarchies unchecked. A group is
                the schema's primary key minus the column being judged, so a
                schema declaring no primary key puts every row in one group.
                Defaults to `None`.

        Returns:
            pa.DataFrameSchema: The converted Pandera DataFrameSchema.
        """
        return cls(schema).convert(
            primary_key_values=primary_key_values,
            foreign_key_values=foreign_key_values,
            dimension_hierarchies=dimension_hierarchies,
        )
