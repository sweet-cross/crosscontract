from typing import Any

import pandas as pd


def rename_columns(df: pd.DataFrame, column_mapping: dict[Any, Any]) -> pd.DataFrame:
    """
    Renames columns in the DataFrame based on the provided mapping.

    Parameters:
        df (pd.DataFrame): The DataFrame to rename columns in.
        column_mapping (dict[Any, Any]): A dictionary where keys are current
            column names and values are new column names.

    Returns:
        pd.DataFrame: A DataFrame with renamed columns.
    """
    return df.rename(columns=column_mapping)


def drop_columns(df: pd.DataFrame, columns_to_drop: list[Any]) -> pd.DataFrame:
    """
    Drops specified columns from the DataFrame.

    Parameters:
        df (pd.DataFrame): The DataFrame to drop columns from.
        columns_to_drop (list[Any]): A list of column names to drop.

    Returns:
        pd.DataFrame: A DataFrame with specified columns dropped.
    """
    return df.drop(columns=columns_to_drop)
