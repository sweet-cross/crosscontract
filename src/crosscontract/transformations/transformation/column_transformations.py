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

    Attributes:
        column_name (str): The name of the column to map values in.
        mapping (dict[Any, Any]): A dictionary where keys are current values
            and values are new values to map to.
        default_value (Any): The value to use for unmapped values. If set to
            `KEEP_ORIGINAL`, unmapped values remain unchanged. If set to `None`,
            unmapped values are explicitly replaced with `None`. Can be set to
            any other fallback value.
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


def cast_type(df: pd.DataFrame, column_name: Any, to_type: type) -> pd.DataFrame:
    """Cast a column to a new type.

    The input DataFrame is not mutated; a new DataFrame is returned.

    Args:
        df (pd.DataFrame): The DataFrame to cast a column in.
        column_name (Any): The name of the column to cast.
        to_type (type): The new type to cast the column to.

    Returns:
        pd.DataFrame: A new DataFrame with the casted column.
    """
    result = df.copy()
    result[column_name] = result[column_name].astype(to_type)
    return result


class CastType(BaseTransformation):
    """Declarative spec for `cast_type`.

    Casts a single column to a new type.

    Attributes:
        column_name (str): The name of the column to cast.
        to_type (str): The new type to cast the column to. Pandas type strings
            (e.g., 'int', 'float', 'str') are accepted.
    """

    type: Literal["cast_column_type"] = Field(
        default="cast_column_type",
        description="Discriminator identifying this transformation.",
    )
    column_name: str = Field(
        description="The name of the column to cast.",
    )
    to_type: str = Field(
        description=(
            "The new type to cast the column to. Pandas type strings "
            "(e.g., 'int', 'float', 'str') are accepted."
        ),
    )

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """Cast the specified column to a new type, returning a new DataFrame.

        Args:
            df (pd.DataFrame): The DataFrame to transform.

        Returns:
            pd.DataFrame: A new DataFrame with the casted column.
        """
        return cast_type(df, self.column_name, self.to_type)


def parse_datetime_column(
    df: pd.DataFrame,
    column_name: Any,
    format: str | None = None,
    dayfirst: bool = False,
) -> pd.DataFrame:
    """Parse a column as datetime.

    The input DataFrame is not mutated; a new DataFrame is returned.

    Args:
        df (pd.DataFrame): The DataFrame to parse a column in.
        column_name (Any): The name of the column to parse.
        format (str | None, optional): The datetime format to use for parsing.
            If `None`, pandas will attempt to infer the format. Defaults to `None`.
        dayfirst (bool, optional): Whether to interpret the first value in
            ambiguous dates as the day. Defaults to `False`.

    Returns:
        pd.DataFrame: A new DataFrame with the parsed datetime column.
    """
    result = df.copy()
    result[column_name] = pd.to_datetime(
        result[column_name], format=format, dayfirst=dayfirst
    )
    return result


class ParseDatetimeColumn(BaseTransformation):
    """Declarative spec for `parse_datetime_column`.

    Parses a single column as datetime.

    Attributes:
        column_name (str): The name of the column to parse.
        format (str | None): The datetime format to use for parsing. If `None`,
            pandas will attempt to infer the format.
        dayfirst (bool): Whether to interpret the first value in ambiguous dates
            as the day.
    """

    type: Literal["parse_datetime_column"] = Field(
        default="parse_datetime_column",
        description="Discriminator identifying this transformation.",
    )
    column_name: str = Field(
        description="The name of the column to parse.",
    )
    format: str | None = Field(
        default=None,
        description=(
            "The datetime format to use for parsing. If `None`, pandas will "
            "attempt to infer the format."
        ),
    )
    dayfirst: bool = Field(
        default=False,
        description=(
            "Whether to interpret the first value in ambiguous dates as the day."
        ),
    )

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """Parse the specified column as datetime, returning a new DataFrame.

        Args:
            df (pd.DataFrame): The DataFrame to transform.

        Returns:
            pd.DataFrame: A new DataFrame with the parsed datetime column.
        """
        return parse_datetime_column(
            df, self.column_name, format=self.format, dayfirst=self.dayfirst
        )
