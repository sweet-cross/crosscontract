from typing import TYPE_CHECKING, Any

import pandas as pd
import pandera.pandas as pa

from ..exceptions import SchemaValidationError

if TYPE_CHECKING:  # pragma: no cover
    from ..schema import TableSchema


def validate_pandas_dataframe(
    schema: "TableSchema",
    df: pd.DataFrame,
    primary_key_values: list[tuple[Any, ...]] | None = None,
    foreign_key_values: dict[tuple[str, ...], list[tuple[Any, ...]]] | None = None,
    skip_primary_key_validation: bool = False,
    skip_foreign_key_validation: bool = False,
    lazy: bool = True,
):
    """Validate a DataFrame against a schema. It allows to provide existing primary key
    and foreign key values for validation. If provided, the primary key uniqueness is
    checked against the union of the existing and the DataFrame values. Similarly,
    foreign key integrity is checked against the union of existing and DataFrame
    values in case of self-referencing foreign keys.

    Args:
        schema (Schema): The schema to validate against.
        df (pd.DataFrame): The DataFrame to validate.
        primary_key_values (list[tuple[Any, ...]] | None): Existing primary key values
            to check for uniqueness.
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
        skip_primary_key_validation (bool): If True, skip primary key validation.
            Default is False.
        skip_foreign_key_validation (bool): If True, skip foreign key validation.
            Default is False.
        lazy (bool): If True, collect all validation errors and raise them together.
            If False, raise the first validation error encountered.
            Default is True.

    Raises:
        SchemaValidationError: If the DataFrame does not conform to the schema.
        ValueError: If a foreign key cannot be validated due to missing referenced
            values.
    """
    pandera_schema = schema.to_pandera_schema()
    pandera_schema.checks = pandera_schema.checks or []

    # Collect dynamic checks in a new list
    additional_checks = []
    if schema.primaryKey and not skip_primary_key_validation:
        additional_checks.append(
            _get_primary_key_check(
                pk_fields=schema.primaryKey.root, primary_key_values=primary_key_values
            )
        )

    if schema.foreignKeys and not skip_foreign_key_validation:
        for fk in schema.foreignKeys:
            valid_values = (
                foreign_key_values.get(tuple(fk.fields)) if foreign_key_values else None
            )
            additional_checks.append(
                _get_foreign_key_check(fk=fk, foreign_key_values=valid_values)
            )
    pandera_schema.checks = (pandera_schema.checks or []) + additional_checks

    # validate the DataFrame
    try:
        pandera_schema.validate(df, lazy=lazy)
    except pa.errors.SchemaErrors as e:
        raise SchemaValidationError(
            message="DataFrame validation against schema failed.", schema_errors=e
        ) from e


def _get_primary_key_check(
    pk_fields: list[str],
    primary_key_values: list[tuple[Any, ...]] | None,
) -> pa.Check:
    """Provide primary key uniqueness checks. The check ensures that primary key values
    are unique within the DataFrame and against existing primary key values.

    Args:
        pk_fields (list[str]): The fields that make up the primary key.
        primary_key_values (list[tuple[Any, ...]] | None): Existing primary key values
            to check for uniqueness.

    Returns:
        pa.Check: A Pandera Check object that can be added to a DataFrameSchema.
    """
    existing_pk_set = set(primary_key_values) if primary_key_values else set()

    def check_primary_key(df_sub: pd.DataFrame) -> pd.Series:
        # 1. Check values in the DataFrame are internally unique
        is_internally_unique = ~df_sub.duplicated(subset=pk_fields, keep=False)

        # 2. Check values against existing primary key values
        is_externally_unique = True
        if existing_pk_set:
            current_keys = pd.MultiIndex.from_frame(df_sub[pk_fields])
            is_externally_unique = ~current_keys.isin(existing_pk_set)

        return is_internally_unique & is_externally_unique

    return pa.Check(
        check_primary_key,
        name=f"PrimaryKeyError: {list(pk_fields)}",
        error=f"PrimaryKeyError: Primary key {pk_fields} is not unique.",
    )


def _get_foreign_key_check(
    fk: Any,
    foreign_key_values: list[tuple[Any, ...]] | None = None,
) -> pa.Check:
    """Provide a single foreign key integrity check. The check ensures that values in
    the foreign key fields exist in the referenced dataset.

    Args:
        fk (ForeignKey): The foreign key to create the check for.
        foreign_key_values list[tuple[Any, ...]] | None):
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
    referenced_fields = fk.reference.fields if fk.reference.resource is None else None

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
        referring_fields: list[str] = fk_fields,
        valid: set = valid_values,
        referenced_fields: list[str] | None = referenced_fields,
    ) -> pd.Series:
        # 1. Prepare valid set for this check
        current_valid = valid.copy()

        # If self-reference, add current dataframe values to valid set
        if referenced_fields is not None:
            internal_reference = df_sub[referenced_fields].apply(tuple, axis=1)
            current_valid = set(current_valid).union(internal_reference)

        # 2. Select the data
        # We interpreting empty strings as nulls
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

    return pa.Check(
        check_fk_integrity,
        name=f"ForeignKeyError: {list(fk_fields)}",
        error=(
            f"ForeignKeyError: Values in {fk_fields} do not exist in referenced table."
        ),
        ignore_na=False,  # We handle NAs explicitly
    )
