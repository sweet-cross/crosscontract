from typing import Any, Literal

import pandas as pd
from pydantic import Field, SerializerFunctionWrapHandler, model_serializer

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
    # `exclude=True` keeps the standard serializer away from the sentinel, which
    # has no serialized form and would crash the JSON encoder. The wrap
    # serializer below puts the key back whenever it holds a real value.
    default_value: Any = Field(
        default=KEEP_ORIGINAL,
        exclude=True,
        description=(
            "Value used for entries absent from `mapping`. When omitted the original"
            " values are kept unchanged. When set to `None`, unmapped values are "
            "replaced with `None`. Can be set to any other fallback value."
        ),
    )

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply the value mapping, returning a new DataFrame.

        Args:
            df (pd.DataFrame): The DataFrame to transform.

        Returns:
            pd.DataFrame: A new DataFrame with the mapped column.
        """
        return map_column_values(df, self.column_name, self.mapping, self.default_value)

    @model_serializer(mode="wrap")
    def _restore_default_value(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, Any]:
        """Re-add `default_value` unless it holds the `KEEP_ORIGINAL` sentinel.

        The field is excluded from the standard serializer, so omitting it is
        the default and an omitted key is exactly what "keep the original
        values" means on reload. Delegating to the handler keeps the standard
        behaviour — the `exclude_*` flags, aliases and JSON conversion — intact.

        Args:
            handler (SerializerFunctionWrapHandler): The standard serializer.

        Returns:
            dict[str, Any]: The serialized model, carrying `default_value` only
                when it was authored.
        """
        data = handler(self)
        if self.default_value is not KEEP_ORIGINAL:
            data["default_value"] = self.default_value
        return data


# Spelled with the Frictionless field-type vocabulary used by
# `contracts/schema/fields/`, not pandas dtype strings. Declared here rather
# than imported: `contracts/` imports from this package, so the reverse import
# would be circular.
CastableType = Literal["integer", "number", "string", "boolean", "datetime"]


def cast_column(
    df: pd.DataFrame, column_name: Any, to_type: CastableType
) -> pd.DataFrame:
    """Cast a column to a new type.

    The input DataFrame is not mutated; a new DataFrame is returned.

    Args:
        df (pd.DataFrame): The DataFrame to cast a column in.
        column_name (Any): The name of the column to cast.
        to_type (CastableType): The new type to cast the column to. Available
            types are:
            - `"integer"`: Casts to pandas nullable integer type (`Int64`).
            - `"number"`: Casts to pandas nullable float type (`Float64`).
            - `"string"`: Casts to pandas string type (`string`).
            - `"boolean"`: Casts to pandas nullable boolean type (`boolean`).
            - `"datetime"`: Raises a ValueError; use
              `parse_datetime_column` for datetime parsing.

    Returns:
        pd.DataFrame: A new DataFrame with the casted column.

    Raises:
        ValueError: If `to_type` is `"datetime"` or is unsupported.
        TypeError: If the column cannot be converted to the specified type.
    """
    result = df.copy()
    match to_type:
        case "integer":
            result[column_name] = pd.to_numeric(
                result[column_name], errors="raise"
            ).astype("Int64")
        case "number":
            result[column_name] = pd.to_numeric(
                result[column_name], errors="raise"
            ).astype("Float64")
        case "string":
            result[column_name] = result[column_name].astype("string")
        case "boolean":
            result[column_name] = result[column_name].astype("boolean")
        case "datetime":
            raise ValueError(
                "Use `parse_datetime_column` to parse a column as datetime."
            )
        case _:
            raise ValueError(f"Unsupported type: {to_type}")
    return result


class CastColumn(BaseTransformation):
    """Declarative spec for `cast_column`.

    Casts a single column to a new type.

    Attributes:
        column_name (str): The name of the column to cast.
        to_type (CastableType): The new type to cast the column to. Available
            types are:
            - `"integer"`: Casts to pandas nullable integer type (`Int64`).
            - `"number"`: Casts to pandas nullable float type (`Float64`).
            - `"string"`: Casts to pandas string type (`string`).
            - `"boolean"`: Casts to pandas nullable boolean type (`boolean`).
            - `"datetime"`: Raises a ValueError; use `parse_datetime_column`
              for datetime parsing.
    """

    type: Literal["cast_column"] = Field(
        default="cast_column",
        description="Discriminator identifying this transformation.",
    )
    column_name: str = Field(
        description="The name of the column to cast.",
    )
    to_type: CastableType = Field(
        description=(
            "The new type to cast the column to, named with the Frictionless "
            "field-type vocabulary: `integer` (nullable `Int64`), `number` "
            "(nullable `Float64`), `string`, or `boolean`. `datetime` is "
            "rejected — use `parse_datetime_column` instead."
        ),
    )

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """Cast the specified column to a new type, returning a new DataFrame.

        Args:
            df (pd.DataFrame): The DataFrame to transform.

        Returns:
            pd.DataFrame: A new DataFrame with the casted column.

        Raises:
            ValueError: If `to_type` is `"datetime"` or is unsupported.
            TypeError: If the column cannot be converted to the specified type.
        """
        return cast_column(df, self.column_name, self.to_type)


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
