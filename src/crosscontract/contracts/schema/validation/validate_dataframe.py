import pandas as pd
import pandera.pandas as pa

from ..exceptions import SchemaValidationError


def validate_dataframe(
    df: pd.DataFrame,
    pandera_schema: pa.DataFrameSchema,
    lazy: bool = True,
) -> pd.DataFrame:
    """Validate a DataFrame against a Pandera DataFrameSchema and provide customized
    exceptions as SchemaValidationError.

    Args:
        df (pd.DataFrame): The DataFrame to validate.
        pandera_schema (pa.DataFrameSchema): The Pandera schema to validate against.
        lazy (bool): If True, collect all validation errors and raise them together.
            If False, raise the first validation error encountered.
            Default is True.

    Raises:
        SchemaValidationError: If the DataFrame does not conform to the schema.

    Raises:
        SchemaValidationError: If the DataFrame does not conform to the schema.
        ValueError: If a foreign key cannot be validated due to missing referenced
            values.

    Returns:
        pd.DataFrame: The validated DataFrame. If validation fails, an exception
            is raised and this return value is not reached.
    """
    try:
        df_out = pandera_schema.validate(df, lazy=lazy)
    except (pa.errors.SchemaErrors, pa.errors.SchemaError) as e:
        raise SchemaValidationError(
            message="DataFrame validation against schema failed.", schema_errors=e
        ) from e
    return df_out
