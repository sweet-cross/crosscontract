from typing import Any

import pandas as pd


def rename_columns(df: pd.DataFrame, column_mapping: dict[Any, Any]) -> pd.DataFrame:
    """Rename columns in the DataFrame according to the provided mapping.

    The input DataFrame is not mutated; a new DataFrame is returned.

    Args:
        df (pd.DataFrame): The DataFrame to rename columns in.
        column_mapping (dict[Any, Any]): A dictionary where keys are current
            column names and values are new column names.

    Returns:
        pd.DataFrame: A new DataFrame with renamed columns.
    """
    return df.rename(columns=column_mapping)


def drop_columns(df: pd.DataFrame, columns_to_drop: list[Any]) -> pd.DataFrame:
    """Drop the specified columns from the DataFrame.

    The input DataFrame is not mutated; a new DataFrame is returned.

    Args:
        df (pd.DataFrame): The DataFrame to drop columns from.
        columns_to_drop (list[Any]): A list of column names to drop.

    Returns:
        pd.DataFrame: A new DataFrame with the specified columns dropped.
    """
    return df.drop(columns=columns_to_drop)
