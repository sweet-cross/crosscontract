"""Basic checks for schema validation."""

from typing import Any, Literal

import pandas as pd
from pydantic import Field, model_validator

from .abstract_base import BaseCheck
from .utils import validate_existing_length_match


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

    @model_validator(mode="after")
    def _validate_existing_length_match(self) -> "IsIn":
        """Ensure every existing value holds one entry per checked column.

        Returns:
            IsIn: The validated check.

        Raises:
            ValueError: If an existing value does not have as many entries as
                there are columns.
        """
        validate_existing_length_match(self.columns, self.existing)
        return self

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

    @model_validator(mode="after")
    def _validate_existing_length_match(self) -> "IsNotIn":
        """Ensure every existing value holds one entry per checked column.

        Returns:
            IsNotIn: The validated check.

        Raises:
            ValueError: If an existing value does not have as many entries as
                there are columns.
        """
        validate_existing_length_match(self.columns, self.existing)
        return self

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


class IsSubsetOf(BaseCheck):
    """Check that the specified columns hold a foreign key: every value that is
    not null appears among the referenced values.

    This follows the SQL `FOREIGN KEY` constraint under `MATCH SIMPLE`, the SQL
    default:

    - A row whose referring columns are null passes. In SQL a null reference
      means "no relationship", not "a broken one", so it is never a violation.
    - For a composite key, one null anywhere in the referring columns is enough
      to pass the row, even when the others hold values. `MATCH FULL`, which
      instead demands that a composite key be either wholly null or wholly
      populated, is not implemented.
    - Every other row must match a referenced value exactly, column by column in
      the declared order.

    Two deliberate departures from SQL:

    - An empty string is read as null. Tabular sources carry no null of their
      own, so a blank cell arrives as `""` and means the same thing.
    - The referenced values are supplied rather than looked up, because a
      contract is validated without access to the referenced table. `allowed`
      carries them for a reference to another contract; `within` names the
      columns of this same frame whose values join the valid set, which is how a
      self-referencing key — a dimension hierarchy — validates against its own
      rows. An empty `allowed` with no `within` therefore means the referenced
      table exists and holds no rows, and every non-null row fails.
    """

    name: Literal["is_subset_of"] = "is_subset_of"
    columns: list[str] = Field(
        description="The columns that hold the foreign key.",
    )
    allowed: list[tuple[Any, ...]] = Field(
        default_factory=list,
        description=(
            "The referenced values. Each tuple holds one value per column, in "
            "the order the columns are declared."
        ),
    )
    within: list[str] | None = Field(
        default=None,
        description=(
            "For a self-referencing key, the columns of this same frame whose "
            "values join the valid set. `None` for a reference to another "
            "contract."
        ),
    )

    ignore_na: bool = Field(
        default=False,
        description=(
            "Whether to ignore NA values in the pandera check logic. Defaults to "
            "`False` because this check decides itself that null rows pass."
        ),
    )

    @model_validator(mode="after")
    def _validate_column_length_match(self) -> "IsSubsetOf":
        """Ensure the referenced values and the referenced columns are as wide
        as the foreign key itself.

        Returns:
            IsSubsetOf: The validated check.

        Raises:
            ValueError: If an allowed value, or the `within` columns, do not
                have as many entries as there are columns.
        """
        validate_existing_length_match(self.columns, self.allowed)
        if self.within is not None and len(self.within) != len(self.columns):
            raise ValueError(
                f"Referenced columns {self.within} must have "
                f"{len(self.columns)} entries to match columns {self.columns}."
            )
        return self

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        """Check that the values in the specified columns are null or appear
        among the referenced values.

        Args:
            df (pd.DataFrame): The DataFrame to validate.

        Returns:
            pd.Series: A boolean Series indicating which rows pass the foreign
                key check.
        """
        valid = set(self.allowed)
        if self.within is not None:
            valid |= set(df[self.within].apply(tuple, axis=1))

        # tabular sources carry no null of their own, so a blank cell is one
        subset = df[self.columns].replace("", pd.NA)
        is_null_row = subset.isna().any(axis=1)
        is_present = pd.Series(
            pd.MultiIndex.from_frame(subset).isin(valid), index=df.index
        )
        return is_present | is_null_row

    def failure_message(self) -> str:
        """Return the failure message for the foreign key check."""
        return (
            f"Columns '{', '.join(self.columns)}' contain values that do not "
            "exist in the referenced values."
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
