"""Basic checks for schema validation."""

from dataclasses import dataclass, field
from typing import Any, Literal

import pandas as pd

from .abstract_base import BaseCheck


@dataclass(kw_only=True)
class IsUnique(BaseCheck):
    """Check one or more columns have jointly unique values. If existing
    values are provided, it also checks against them for uniqueness.

    Args:
        columns (list[str]): The columns that should have jointly unique values.
        label (str): The label or column name the check applies to.
        expected (ClassVar[bool], optional): The expected outcome of the check.
            Defaults to True.
        ignore_na (bool, optional): Whether to ignore NA values in the pandera
            check logic.
            Defaults to True (pandera default).
    """

    name: Literal["is_unique"] = "is_unique"
    columns: list[str]

    def validate(self, df: pd.DataFrame) -> pd.Series:
        """Check that the specified columns have unique values.

        Args:
            df (pd.DataFrame): The DataFrame to validate.
        Returns:
            pd.Series: A boolean Series indicating which rows pass the uniqueness
                check.
        """
        return ~df.duplicated(subset=self.columns, keep=False)

    def failure_message(self) -> str:
        """Return the failure message for the uniqueness check."""
        return (
            f"Column '{self.label}' must have unique values."
            if self.expected
            else f"Column '{self.label}' must not have unique values."
        )


@dataclass(kw_only=True)
class IsIn(BaseCheck):
    """Check that the specified columns do not contain any of the existing values.

    Args:
        columns (list[str]): The columns that should have jointly unique values.
        existing (list[tuple[Any, ...]] | None): The existing values that should
            not be present in the columns.
        label (str): The label or column name the check applies to.
        expected (bool, optional): The expected outcome of the check.
            Defaults to True.
        ignore_na (bool, optional): Whether to ignore NA values in the pandera
            check logic.
            Defaults to True (pandera default).
    """

    name: Literal["is_in"] = "is_in"
    columns: list[str]
    existing: list[tuple[Any, ...]] = field(default_factory=list)

    def validate(self, df: pd.DataFrame) -> pd.Series:
        """Check that the values in the specified columns are in the list of
        the allowed values provided.

        Args:
            df (pd.DataFrame): The DataFrame to validate.

        Returns:
            pd.Series: A boolean Series indicating which rows pass the is-in check.
        """
        if not self.existing:
            # No existing values to check against, so all fail the check
            return pd.Series(False, index=df.index)
        current_keys = pd.MultiIndex.from_frame(df[self.columns])

        return current_keys.isin(self.existing)

    def failure_message(self) -> str:
        """Return the failure message for the is-in check."""
        return (
            (
                f"Columns '{', '.join(self.columns)}' values are "
                "not in the provided values."
            )
            if self.expected
            else (
                f"Columns '{', '.join(self.columns)}' contain values that are "
                "in the provided values."
            )
        )


@dataclass(kw_only=True)
class IsNotNull(BaseCheck):
    """Check that the specified columns do not contain null values.

    Args:
        columns (list[str]): The columns that should have jointly unique values.
        existing (list[tuple[Any, ...]] | None): The existing values that should
            not be present in the columns.
        label (str): The label or column name the check applies to.
        expected (bool): Whether the columns are expected to have no null values.
        ignore_na (bool, optional): Whether to ignore NA values in the pandera
            check logic.
            Defaults to False.
    """

    name: Literal["is_not_null"] = "is_not_null"
    columns: list[str]

    ignore_na: bool = False

    def validate(self, df: pd.DataFrame) -> pd.Series:
        """Check that the specified columns do not contain null values.

        Args:
            df (pd.DataFrame): The DataFrame to validate.

        Returns:
            pd.Series: A boolean Series indicating which rows pass the is-not-null
                check.
        """
        return ~df[self.columns].isnull().any(axis=1)

    def failure_message(self) -> str:
        """Return the failure message for the is-not-null check."""
        return (
            f"Columns '{', '.join(self.columns)}' contain null values."
            if self.expected
            else (
                f"Columns '{', '.join(self.columns)}' contain no null values, "
                "but nulls were expected."
            )
        )
