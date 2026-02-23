from datetime import UTC
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:  # pragma: no cover
    from crosscontract.contracts.schema import TableSchema

import pandera.pandas as pa
from pandera.engines import pandas_engine

from crosscontract.contracts.schema.fields import (
    DateTimeField,
    IntegerField,
    ListField,
    NumberField,
    StringField,
)
from crosscontract.contracts.schema.fields.base import BaseField
from crosscontract.contracts.schema.reference.foreign_key import ForeignKey

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

    def convert(
        self,
        name: str = "ConvertedSchema",
        primary_key_values: list[tuple[Any, ...]] | None = None,
        foreign_key_values: dict[tuple[str, ...], list[tuple[Any, ...]]] | None = None,
        skip_primary_key_validation: bool = False,
        skip_foreign_key_validation: bool = False,
    ) -> pa.DataFrameSchema:
        """Convert the given TableSchema into a Pandera DataFrameSchema.

        Args:
            name (str): The name of the resulting DataFrameSchema.
            primary_key_values (list[tuple[Any, ...]] | None): Existing primary key
                values to check for uniqueness.
                Note: The uniqueness of the primary key is validated is checked against
                    the union of the provided values and the values in the DataFrame.
            foreign_key_values (dict[tuple[str, ...], list[tuple[Any, ...]]] | None):
                Existing foreign key values to check against. This is provided as a
                dictionary where the keys are the tuples of fields that refer to the
                referenced values, and the values are lists of tuples representing the
                existing referenced values.
                Note: In the case of self-referencing foreign keys, the values in the
                    DataFrame are considered automatically, i.e., the referring fields
                    are validated against the union of the provided values and the
                    values in the DataFrame.
            skip_primary_key_validation (bool): Whether to skip the validation of
                primary key uniqueness.
            skip_foreign_key_validation (bool): Whether to skip the validation of
                foreign key integrity.

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

        # create the pandera schema with the columns and the name
        pandera_schema = pa.DataFrameSchema(
            columns=columns,
            index=None,  # Currently we do not support index columns
            name=name,
            coerce=True,  # Useful for CSVs (str -> int)
            strict=True,  # Fails if DataFrame contains columns not in Schema
        )

        # Handle primary key constraints by adding a custom check to the schema
        additional_checks: list[pa.Check] = []
        if self.schema.primaryKey and not skip_primary_key_validation:
            self._check_reference_inputs(primary_key_values)  # Validate input format
            additional_checks.append(
                self._get_primary_key_check(
                    pk_fields=self.schema.primaryKey.root,
                    primary_key_values=primary_key_values,
                )
            )

        # Handle foreign key constraints by adding custom checks to the schema
        if self.schema.foreignKeys and not skip_foreign_key_validation:
            for fk in self.schema.foreignKeys:
                valid_values = (
                    foreign_key_values.get(tuple(fk.fields))
                    if foreign_key_values
                    else None
                )
                self._check_reference_inputs(valid_values)  # Validate input format
                additional_checks.append(
                    self._get_foreign_key_check(fk=fk, foreign_key_values=valid_values)
                )

        # add the additional checks to the pandera schema checks, ensuring we
        # don't overwrite any existing checks
        pandera_schema.checks = (pandera_schema.checks or []) + additional_checks

        return pandera_schema

    @classmethod
    def convert_schema(
        cls,
        schema: "TableSchema",
        name: str = "ConvertedSchema",
        primary_key_values: list[tuple[Any, ...]] | None = None,
        foreign_key_values: dict[tuple[str, ...], list[tuple[Any, ...]]] | None = None,
        skip_primary_key_validation: bool = False,
        skip_foreign_key_validation: bool = False,
    ) -> pa.DataFrameSchema:
        """Class method to convert a TableSchema into a Pandera DataFrameSchema without
        needing to instantiate the adapter.

        Args:
            schema (TableSchema): The TableSchema to convert.
            name (str): The name of the resulting DataFrameSchema.
            primary_key_values (list[tuple[Any, ...]] | None): Existing primary key
                values to check for uniqueness.
                Note: The uniqueness of the primary key is validated is checked against
                    the union of the provided values and the values in the DataFrame.
            foreign_key_values (dict[tuple[str, ...], list[tuple[Any, ...]]] | None):
                Existing foreign key values to check against. This is provided as a
                dictionary where the keys are the tuples of fields that refer to the
                referenced values, and the values are lists of tuples representing the
                existing referenced values.
                Note: In the case of self-referencing foreign keys, the values in the
                    DataFrame are considered automatically, i.e., the referring fields
                    are validated against the union of the provided values and the
                    values in the DataFrame.
            skip_primary_key_validation (bool): Whether to skip the validation of
                primary key uniqueness.
            skip_foreign_key_validation (bool): Whether to skip the validation of
                foreign key integrity.

        Returns:
            pa.DataFrameSchema: A Pandera DataFrameSchema representing the schema of the
                data described by the TableSchema.
        """
        return super().convert_schema(
            schema,
            name=name,
            primary_key_values=primary_key_values,
            skip_primary_key_validation=skip_primary_key_validation,
            foreign_key_values=foreign_key_values,
            skip_foreign_key_validation=skip_foreign_key_validation,
        )

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
            pandera_type = "Int64"
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
            "integer": list[int],
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
        kwargs = self._init_pandera_kwargs(
            field,
            pandas_engine.DateTime(tz=UTC, to_datetime_kwargs={"format": field.format}),
        )

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

    @staticmethod
    def _check_reference_inputs(given: Any):
        """Check that the given input for reference validation is in the correct
        format, i.e., a list of tuples

        Args:
            given (Any): The input to check.

        Raises:
            ValueError: If the input is not a list of tuples.
        """
        if given is None:
            return
        # check outer structure is a list, set, or tuple:
        raise_error = False
        if not isinstance(given, (list, set, tuple)):
            raise_error = True
        # check that the inner structure is a tuple:
        elif not all(isinstance(item, tuple) for item in given):
            raise_error = True
        if raise_error:
            raise ValueError(
                "Existing references must be must be provided as a list of tuples, "
                "where each tuple represents a valid referenced key. Example: "
                "[(10,), (11,)] and not [10, 11] or [[10], [11]]."
            )

    @staticmethod
    def _check_pk_integrity(
        df_sub: pd.DataFrame,
        pk_fields: list[str],
        existing_pk_set: set[tuple[Any, ...]],
    ) -> pd.Series:
        # 1. Ensure no nulls in the columns
        has_nulls = df_sub[pk_fields].isna().any(axis=1)

        # 2. Check values in the DataFrame are internally unique
        is_internally_unique = ~df_sub.duplicated(subset=pk_fields, keep=False)

        # 3. Check values against existing primary key values
        if existing_pk_set:
            current_keys = pd.MultiIndex.from_frame(df_sub[pk_fields])
            is_externally_unique = pd.Series(
                ~current_keys.isin(existing_pk_set),
                index=df_sub.index,
            )
            return is_internally_unique & is_externally_unique & ~has_nulls
        return is_internally_unique & ~has_nulls

    @staticmethod
    def _get_primary_key_check(
        pk_fields: list[str],
        primary_key_values: list[tuple[Any, ...]] | None,
    ) -> pa.Check:
        """Provide primary key uniqueness checks. The check ensures that primary
        key values are unique within the DataFrame and against existing primary
        key values.

        Args:
            pk_fields (list[str]): The fields that make up the primary key.
            primary_key_values (list[tuple[Any, ...]] | None): Existing primary
                key values to check for uniqueness.

        Returns:
            pa.Check: A Pandera Check object that can be added to a DataFrameSchema.
        """
        existing_pk_set = set(primary_key_values) if primary_key_values else set()

        def check_pk_integrity(df_sub: pd.DataFrame) -> pd.Series:
            return PanderaPandasAdapter._check_pk_integrity(
                df_sub=df_sub,
                pk_fields=pk_fields,
                existing_pk_set=existing_pk_set,
            )

        return pa.Check(
            check_pk_integrity,
            name=f"PrimaryKeyError: {list(pk_fields)}",
            error=(
                f"PrimaryKeyError: Primary key {pk_fields} must be non-null and "
                "unique within the dataset and compared to existing primary key values."
            ),
        )

    @staticmethod
    def _check_fk_integrity(
        df_sub: pd.DataFrame,
        fk_fields: list[str],
        valid_values: set,
        referenced_fields: list[str] | None,
    ) -> pd.Series:
        """Check function for the integrity of a foreign key constraint of a
        DataFrame. The function checks whether the values in the foreign key
        fields of the DataFrame exist in the set of valid referenced values,
        which is the union of the provided valid values and the values in the
        DataFrame itself in case of self-referencing foreign keys.

        The function is usually not directly called, but is used within a Pandera
        check

        Args:
            df_sub (pd.DataFrame): The DataFrame to check.
            fk_fields (list[str]): The fields that make up the foreign key.
            valid_values (set): The set of valid referenced values to check against.
            referenced_fields (list[str] | None): The fields in the DataFrame that
                hold the values to check against in case of self-referencing foreign
                keys. If None, it is assumed that this is not a self-referencing
                foreign key.

        Returns:
            pd.Series: A boolean Series indicating whether each row in the DataFrame
                satisfies the foreign key constraint.
        """
        # 1. Prepare valid set for this check
        current_valid = valid_values.copy()

        # If self-reference, add current dataframe values to valid set
        if referenced_fields is not None:
            internal_reference = df_sub[referenced_fields].apply(tuple, axis=1)
            current_valid = set(current_valid).union(internal_reference)

        # 2. Select the data
        # We interpret empty strings as nulls
        subset = df_sub[fk_fields].replace("", pd.NA)

        # 3. Identify rows containing Nulls
        # (Standard SQL: Nulls pass FK check)
        is_null_row = subset.isna().any(axis=1)

        # 4. Create a tuple for all rows
        keys_to_check = pd.MultiIndex.from_frame(subset)

        # 5. Check Existence
        # This returns a boolean Series aligned with df_sub.index
        is_present = keys_to_check.isin(current_valid)

        # 6. Final Logic: Valid if (Present in Reference) OR (Is Null)
        return is_present | is_null_row

    @staticmethod
    def _get_foreign_key_check(
        fk: ForeignKey,
        foreign_key_values: list[tuple[Any, ...]] | None = None,
    ) -> pa.Check:
        """Provide a single foreign key integrity check. The check ensures that values
        in the foreign key fields exist in the referenced dataset.

        Args:
            fk (ForeignKey): The foreign key to create the check for.
            foreign_key_values (list[tuple[Any, ...]] | None):
                Existing foreign key values to check against.

        Returns:
            pa.Check: A Pandera Check object that can be added to a DataFrameSchema.

        Raises:
            ValueError: If no referenced values are provided for validation.
        """
        fk_fields = fk.fields

        # Get external valid values
        valid_values = set(foreign_key_values) if foreign_key_values else set()

        # Handle Self-Reference
        # the fields that hold the valid values in case of self-reference
        referenced_fields = (
            fk.reference.fields if fk.reference.resource is None else None
        )

        # If no external values and not self-reference, we can't validate
        # so we raise a ValueError
        if not valid_values and referenced_fields is None:
            raise ValueError(
                f"Cannot validate foreign key {fk_fields} as no referenced values "
                "are provided."
            )

        # Capture closure variables
        def check_fk_integrity(
            df_sub: pd.DataFrame,
        ) -> pd.Series:
            return PanderaPandasAdapter._check_fk_integrity(
                df_sub=df_sub,
                fk_fields=fk_fields,
                valid_values=valid_values,
                referenced_fields=referenced_fields,
            )

        return pa.Check(
            check_fk_integrity,
            name=f"ForeignKeyError: {list(fk_fields)}",
            error=(
                f"ForeignKeyError: Values in {fk_fields} do not exist in referenced "
                f"table."
            ),
            ignore_na=False,  # We handle NAs explicitly
        )
