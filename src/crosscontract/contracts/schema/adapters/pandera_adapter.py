from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from crosscontract.contracts.schema import TableSchema

import pandera.pandas as pa
from pandas import Int64Dtype

from crosscontract.contracts.schema.fields import (
    DateTimeField,
    IntegerField,
    ListField,
    NumberField,
    StringField,
)
from crosscontract.contracts.schema.fields.base import BaseField

from .abstract_adapter import AbstractAdapter
from .utils import parse_datetime


def convert_schema_to_pandera(
    schema: "TableSchema",
    name: str = "ConvertedSchema",
) -> pa.DataFrameSchema:
    """Convert the DataContract to a Pandera DataFrameSchema.

    Args:
        schema (TableSchema): The Schema instance to convert.
        name (str): The name of the resulting DataFrameSchema.

    Returns:
        pa.DataFrameSchema: A Pandera DataFrameSchema representing the schema of the
            data described by the Schema.
    """
    return PanderaPandasAdapter.convert_schema(schema, name=name)


class PanderaPandasAdapter(AbstractAdapter):
    """Adapter that converts a schema into a corresponding pandera schema that
    allows to validate a Pandas DataFrame against the schema.
    """

    def convert(self, name: str = "ConvertedSchema") -> pa.DataFrameSchema:
        """Convert the given TableSchema into a Pandera DataFrameSchema.

        Args:
            name (str): The name of the resulting DataFrameSchema.

        Returns:
            pa.DataFrameSchema: A Pandera DataFrameSchema representing the schema
                of the data described by the TableSchema.
        """
        columns: dict[str, pa.Column] = {}
        for field in self.schema.field_iterator():
            match field:
                case IntegerField() | NumberField():
                    columns[field.name] = self._convert_numeric_field(field)
                case StringField():
                    columns[field.name] = self._convert_string_field(field)
                case DateTimeField():
                    columns[field.name] = self._convert_datetime_field(field)
                case ListField():
                    columns[field.name] = self._convert_list_field(field)
                case _:  # pragma: no cover
                    # this should never happen because the schema validation should
                    # catch unsupported field types, but we add this case for type
                    # safety
                    raise NotImplementedError(
                        f"Field type '{field.type}' not yet supported"
                    )
        return pa.DataFrameSchema(
            columns=columns,
            index=None,  # Currently we do not support index columns
            name=name,
            coerce=True,  # Useful for CSVs (str -> int)
            strict=True,  # Fails if DataFrame contains columns not in Schema
        )

    @classmethod
    def convert_schema(
        cls, schema: "TableSchema", name: str = "ConvertedSchema"
    ) -> pa.DataFrameSchema:
        """Class method to convert a TableSchema into a Pandera DataFrameSchema without
        needing to instantiate the adapter.

        Args:
            schema (TableSchema): The TableSchema to convert.
            name (str): The name of the resulting DataFrameSchema.

        Returns:
            pa.DataFrameSchema: A Pandera DataFrameSchema representing the schema of the
                data described by the TableSchema.
        """
        return super().convert_schema(schema, name=name)

    def _init_pandera_kwargs(
        self, field: BaseField, pandera_type: type | str
    ) -> dict[str, Any]:
        """Initialize the keyword arguments for creating a pandera Column based on
        the given field.

        Args:
            field (BaseField): The field for which to initialize the pandera kwargs.
            pandera_type (type | str): The pandera type for the field.

        Returns:
            dict[str, Any]: The initialized keyword arguments for creating a pandera
                Column.
        """
        kwargs: dict[str, Any] = {
            "name": field.name,
            "dtype": pandera_type,
            "title": field.title,
            "description": field.description,
            "checks": [],
        }

        kwargs["required"] = field.constraints.required
        if not kwargs["required"]:
            kwargs["nullable"] = True
        kwargs["unique"] = field.constraints.unique

        # check constraints
        # Handle enum constraint
        if enum_constraint := getattr(field.constraints, "enum", None):
            kwargs["checks"].append(pa.Check.isin(enum_constraint))
        return kwargs

    def _convert_numeric_field(self, field: IntegerField | NumberField) -> pa.Column:
        """Convert a numeric field (IntegerField or NumberField) into a pandera
        Column definition.

        Args:
            field (IntegerField | NumberField): The numeric field to convert.

        Returns:
            pa.Column: A pandera Column representing the numeric field.
        """
        pandera_type: type | str | None = None
        if isinstance(field, IntegerField):
            pandera_type = Int64Dtype
        elif isinstance(field, NumberField):
            pandera_type = float
        else:
            raise ValueError("Field must be an IntegerField or NumberField")

        kwargs = self._init_pandera_kwargs(field, pandera_type)

        # Handle minimum and maximum constraints
        if field.constraints.minimum is not None:
            kwargs["checks"].append(pa.Check.ge(field.constraints.minimum))
        if field.constraints.maximum is not None:
            kwargs["checks"].append(pa.Check.le(field.constraints.maximum))

        return pa.Column(**kwargs)

    def _convert_string_field(self, field: StringField) -> pa.Column:
        """Convert a StringField into a pandera Column definition.

        Args:
            field (StringField): The StringField to convert.

        Returns:
            pa.Column: A pandera Column representing the StringField.
        """
        kwargs = self._init_pandera_kwargs(field, str)

        # Handle pattern constraint
        if field.constraints.pattern is not None:
            kwargs["regex"] = field.constraints.pattern

        # Handle minLength and maxLength constraints
        if (
            field.constraints.minLength is not None
            or field.constraints.maxLength is not None
        ):
            kwargs["checks"].append(
                pa.Check.str_length(
                    min_value=field.constraints.minLength,
                    max_value=field.constraints.maxLength,
                )
            )

        return pa.Column(**kwargs)

    def _convert_list_field(self, field: ListField) -> pa.Column:
        """Convert a ListField into a pandera Column definition.

        Args:
            field (ListField): The ListField to convert.

        Returns:
            pa.Column: A pandera Column representing the ListField.
        """
        # determine the pandera type for the list items
        type_mapping: dict[str, type | str] = {
            "string": list[str],
            "integer": list[Int64Dtype],
            "number": list[float],
            "boolean": list[bool],
        }
        pandera_type = type_mapping.get(field.itemType)
        if pandera_type is None:  # pragma: no cover
            # this is already validated at the schema level, so this should never
            # happen but we add this check for type safety
            raise ValueError(f"Unsupported itemType: {field.itemType}")

        # initialize the pandera kwargs for the list field
        kwargs = self._init_pandera_kwargs(field, pandera_type)

        # Handle minLength and maxLength constraints
        if field.constraints.minLength is not None:
            kwargs["checks"].append(
                pa.Check(
                    lambda s: s.apply(
                        lambda lst, m=field.constraints.minLength: len(lst) >= m
                    )
                )
            )
        if field.constraints.maxLength is not None:
            kwargs["checks"].append(
                pa.Check(
                    lambda s: s.apply(
                        lambda lst, m=field.constraints.maxLength: len(lst) <= m
                    )
                )
            )

        return pa.Column(**kwargs)

    def _convert_datetime_field(self, field: DateTimeField) -> pa.Column:
        """Convert a DateTimeField into a pandera Column definition.

        Args:
            field (DateTimeField): The DateTimeField to convert.

        Returns:
            pa.Column: A pandera Column representing the DateTimeField.
        """
        kwargs = self._init_pandera_kwargs(field, datetime)

        # Handle minimum and maximum constraints
        if field.constraints.minimum is not None:
            minimum = field.constraints.minimum
            kwargs["checks"].append(
                pa.Check(
                    lambda s: s.apply(
                        lambda dt, m=minimum, fmt=field.format: parse_datetime(dt, fmt)  # type: ignore[operator]
                        >= parse_datetime(m, fmt)
                    )
                )
            )
        if field.constraints.maximum is not None:
            maximum = field.constraints.maximum
            kwargs["checks"].append(
                pa.Check(
                    lambda s: s.apply(
                        lambda dt, m=maximum, fmt=field.format: parse_datetime(dt, fmt)  # type: ignore[operator]
                        <= parse_datetime(m, fmt)
                    )
                )
            )

        return pa.Column(**kwargs)
