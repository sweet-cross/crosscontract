from typing import Any

import pandas as pd

# Define a sentinel value
KEEP_ORIGINAL = object()


def map_column_values(
    df: pd.DataFrame,
    column_name: Any,
    value_mapping: dict[Any, Any],
    default_value: Any = KEEP_ORIGINAL,
) -> pd.DataFrame:
    """Map values in a column according to the provided mapping.

    The input DataFrame is not mutated; a new DataFrame is returned.

    Args:
        df (pd.DataFrame): The DataFrame to map column values in.
        column_name (Any): The name of the column to map values in.
        value_mapping (dict[Any, Any]): A dictionary where keys are current
            values and values are new values to map to.
        default_value (Any, optional): The value to use for unmapped values.
            If set to `KEEP_ORIGINAL` (the default), unmapped values remain
            unchanged. If set to `None`, unmapped values are explicitly
            replaced with `None`. Can be set to any other fallback value.
            Defaults to `KEEP_ORIGINAL`.

    Returns:
        pd.DataFrame: A new DataFrame with the mapped column.
    """
    # Create the mapped series. Note: pandas .map() turns unmapped values into NaNs.
    mapped_series = df[column_name].map(value_mapping)

    # Identify which values were NOT in the dictionary keys
    unmapped_mask = ~df[column_name].isin(value_mapping.keys())

    if default_value is KEEP_ORIGINAL:
        # Keep original values where no mapping was provided
        final_series = mapped_series.where(~unmapped_mask, df[column_name])
    else:
        # Fill unmapped values with the specified default (e.g., None, "Unknown", etc.)
        final_series = mapped_series.where(~unmapped_mask, default_value)

    return df.assign(**{column_name: final_series})
