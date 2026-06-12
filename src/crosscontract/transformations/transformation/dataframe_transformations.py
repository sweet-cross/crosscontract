from typing import Any, Literal

import pandas as pd
from pydantic import Field

from .base import BaseTransformation


def rename_columns(df: pd.DataFrame, column_mapping: dict[Any, Any]) -> pd.DataFrame:
    """Rename columns in the DataFrame according to the provided mapping.

    The input DataFrame is not mutated; a new DataFrame is returned.

    Args:
        df (pd.DataFrame): The DataFrame to rename columns in.
        column_mapping (dict[Any, Any]): A dictionary where keys are current
            column names and values are new column names.

    Returns:
        pd.DataFrame: A new DataFrame with renamed columns.

    Raises:
        KeyError: If any key in `column_mapping` is not a column of `df`.
        ValueError: If the rename would produce duplicate column labels.
    """
    renamed = df.rename(columns=column_mapping, errors="raise")
    if renamed.columns.has_duplicates:
        dupes = renamed.columns[renamed.columns.duplicated()].unique().tolist()
        raise ValueError(f"Rename produces duplicate column(s): {dupes}")
    return renamed


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


class RenameColumns(BaseTransformation):
    """Declarative spec for `rename_columns`.

    Renames columns according to `mapping` (current name to new name).
    """

    type: Literal["rename_columns"] = Field(
        default="rename_columns",
        description="Discriminator identifying this transformation.",
    )
    mapping: dict[str, str] = Field(
        description="Maps current column names (keys) to new names.",
    )

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rename columns, returning a new DataFrame.

        Args:
            df (pd.DataFrame): The DataFrame to transform.

        Returns:
            pd.DataFrame: A new DataFrame with renamed columns.
        """
        return rename_columns(df, self.mapping)


class DropColumns(BaseTransformation):
    """Declarative spec for `drop_columns`.

    Drops the columns listed in `columns`.
    """

    type: Literal["drop_columns"] = Field(
        default="drop_columns",
        description="Discriminator identifying this transformation.",
    )
    columns: list[str] = Field(
        description="The column names to drop.",
    )

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """Drop the listed columns, returning a new DataFrame.

        Args:
            df (pd.DataFrame): The DataFrame to transform.

        Returns:
            pd.DataFrame: A new DataFrame with the columns dropped.
        """
        return drop_columns(df, self.columns)
