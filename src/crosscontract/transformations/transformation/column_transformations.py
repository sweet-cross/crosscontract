from typing import Any, Literal

import pandas as pd
from pydantic import Field

from .base import BaseTransformation

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

    # Label-based assignment on a copy: keeps the input unmutated and, unlike
    # df.assign(**{...}), supports non-string column labels.
    result = df.copy()
    result[column_name] = final_series
    return result


class MapColumnValues(BaseTransformation):
    """Declarative spec for `map_column_values`.

    Remaps the values of a single column according to `mapping`, with control
    over how unmapped values are handled via `default_value`.
    """

    type: Literal["map_column_values"] = Field(
        default="map_column_values",
        description="Discriminator identifying this transformation.",
    )
    column_name: str = Field(
        description="The name of the column to map values in.",
    )
    mapping: dict[Any, Any] = Field(
        description="Maps current values (keys) to new values.",
    )
    default_value: Any = Field(
        default=None,
        description=(
            "Value used for entries absent from `mapping`. When omitted or "
            "`None`, unmapped values are kept unchanged."
        ),
    )

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply the value mapping, returning a new DataFrame.

        A `default_value` of `None` is interpreted as "keep original"; the spec
        therefore cannot remap unmapped entries to `None` (use the
        `map_column_values` function directly for that).

        Args:
            df (pd.DataFrame): The DataFrame to transform.

        Returns:
            pd.DataFrame: A new DataFrame with the mapped column.
        """
        default_value = (
            KEEP_ORIGINAL if self.default_value is None else self.default_value
        )
        return map_column_values(df, self.column_name, self.mapping, default_value)
