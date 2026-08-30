"""Composite checks for schema references."""

from typing import Any, Literal

import pandas as pd
import pandera.pandas as pa
from pydantic import Field, model_validator

from .abstract_base import BaseCheck
from .base_checks import IsNotIn, IsNotNull, IsUnique


class IsValidPrimaryKey(BaseCheck):
    """Check if the column is a valid primary key (unique and non-null).
    If existing values are provided, it also checks against them for uniqueness.
    """

    name: Literal["is_valid_primary_key"] = "is_valid_primary_key"

    columns: list[str] = Field(
        description="List of column names that constitute the primary key.",
    )
    existing: list[tuple[Any, ...]] = Field(
        default_factory=list,
        description=(
            "Existing values to check against for uniqueness. Each tuple "
            "represents one existing primary key."
        ),
    )

    @model_validator(mode="after")
    def _validate_existing_length_match(self) -> "IsValidPrimaryKey":
        """Ensure every existing key holds one entry per primary key column.

        Returns:
            IsValidPrimaryKey: The validated check.

        Raises:
            ValueError: If an existing key does not have as many entries as
                there are columns.
        """
        mismatched = [t for t in self.existing if len(t) != len(self.columns)]
        if mismatched:
            raise ValueError(
                f"Existing values must have {len(self.columns)} entries to match "
                f"columns {self.columns}, but got {mismatched}."
            )
        return self

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        """Check that the specified columns form a valid primary key
        (unique and non-null)."""
        is_unique = IsUnique(label=self.label, columns=self.columns)(df)
        is_not_null = IsNotNull(
            label=self.label, columns=self.columns, ignore_na=False
        )(df)
        # we could skip this check if self.existing is empty, but its cheap
        # anyways to we keep the behavior as in the pandera checks.
        is_externally_unique = IsNotIn(
            label=self.label,
            columns=self.columns,
            existing=self.existing,
        )(df)
        return is_unique & is_not_null & is_externally_unique

    def to_pandera(self) -> list[pa.Check]:
        """Unpack the individual foundational checks into Pandera checks."""
        return [
            # Unpack the lists returned by the foundational checks
            *IsNotNull(
                label=self.label, columns=self.columns, ignore_na=False
            ).to_pandera(),
            *IsUnique(label=self.label, columns=self.columns).to_pandera(),
            *IsNotIn(
                label=self.label,
                columns=self.columns,
                existing=self.existing,
            ).to_pandera(),
        ]
