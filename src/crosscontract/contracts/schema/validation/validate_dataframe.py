from typing import TYPE_CHECKING, Any, Literal

import pandas as pd
import pandera.pandas as pa

from ..exceptions import SchemaValidationError

if TYPE_CHECKING:  # pragma: no cover
    from ..schema import TableSchema
from ..adapters.pandera_adapter import PanderaPandasAdapter


def validate_dataframe(
    schema: "TableSchema",
    df: pd.DataFrame,
    primary_key_values: list[tuple[Any, ...]] | None = None,
    foreign_key_values: dict[tuple[str, ...], list[tuple[Any, ...]]] | None = None,
    skip_primary_key_validation: bool = False,
    skip_foreign_key_validation: bool = False,
    lazy: bool = True,
) -> pd.DataFrame:
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

    Returns:
        pd.DataFrame: The validated DataFrame. If validation fails, an exception
            is raised and this return value is not reached.
    """
    # get the pandera schema
    pandera_schema = PanderaPandasAdapter.convert_schema(
        schema,
        primary_key_values=primary_key_values,
        foreign_key_values=foreign_key_values,
        skip_primary_key_validation=skip_primary_key_validation,
        skip_foreign_key_validation=skip_foreign_key_validation,
    )
    # validate the DataFrame
    try:
        df_out = pandera_schema.validate(df, lazy=lazy)
    except (pa.errors.SchemaErrors, pa.errors.SchemaError) as e:
        raise SchemaValidationError(
            message="DataFrame validation against schema failed.", schema_errors=e
        ) from e
    return df_out
