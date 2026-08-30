"""Basic checks for schema validation."""

from typing import Any, Literal

import pandas as pd
from pydantic import Field

from .abstract_base import BaseCheck


class IsUnique(BaseCheck):
    """Check one or more columns have jointly unique values."""

    name: Literal["is_unique"] = "is_unique"
    columns: list[str] = Field(
        description="The columns that should have jointly unique values.",
    )

    def __call__(self, df: pd.DataFrame) -> pd.Series:
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
        return f"Column '{self.label}' must have unique values."


class IsIn(BaseCheck):
    """Check that the specified columns only contain existing values."""

    name: Literal["is_in"] = "is_in"
    columns: list[str] = Field(
        description="The columns whose values are checked against the existing values.",
    )
    existing: list[tuple[Any, ...]] = Field(
        default_factory=list,
        description=(
            "The existing values the columns are checked against. Each tuple "
            "represents one referenced key."
        ),
    )

    def __call__(self, df: pd.DataFrame) -> pd.Series:
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

        return pd.Series(current_keys.isin(self.existing), index=df.index)

    def failure_message(self) -> str:
        """Return the failure message for the is-in check."""
        return (
            f"Columns '{', '.join(self.columns)}' values are "
            "not in the provided values."
        )


class IsNotIn(BaseCheck):
    """Check that the specified columns do not contain any of the existing values."""

    name: Literal["is_not_in"] = "is_not_in"
    columns: list[str] = Field(
        description="The columns whose values are checked against the existing values.",
    )
    existing: list[tuple[Any, ...]] = Field(
        default_factory=list,
        description=(
            "The existing values the columns are checked against. Each tuple "
            "represents one referenced key."
        ),
    )

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        """Check that the values in the specified columns are not in the list of
        the disallowed values provided.

        Args:
            df (pd.DataFrame): The DataFrame to validate.

        Returns:
            pd.Series: A boolean Series indicating which rows pass the is-not-in check.
        """
        if not self.existing:
            # No existing values to check against, so all pass the check
            return pd.Series(True, index=df.index)
        current_keys = pd.MultiIndex.from_frame(df[self.columns])

        return pd.Series(~current_keys.isin(self.existing), index=df.index)

    def failure_message(self) -> str:
        """Return the failure message for the is-not-in check."""
        return (
            f"Columns '{', '.join(self.columns)}' contain values that are "
            "in the provided values."
        )


class IsNotNull(BaseCheck):
    """Check that the specified columns do not contain null values."""

    name: Literal["is_not_null"] = "is_not_null"
    columns: list[str] = Field(
        description="The columns that should not contain null values.",
    )

    ignore_na: bool = Field(
        default=False,
        description=(
            "Whether to ignore NA values in the pandera check logic. Defaults to "
            "`False` because this check inspects the NA values itself."
        ),
    )

    def __call__(self, df: pd.DataFrame) -> pd.Series:
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
        return f"Columns '{', '.join(self.columns)}' contain null values."
