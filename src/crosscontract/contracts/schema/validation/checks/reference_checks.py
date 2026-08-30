from dataclasses import dataclass, field
from typing import Any, Literal

import pandas as pd
import pandera.pandas as pa

from .abstract_base import BaseCheck
from .base_checks import IsIn, IsNotNull, IsUnique


@dataclass(kw_only=True)
class IsValidPrimaryKey(BaseCheck):
    """Check if the column is a valid primary key (unique and non-null).
    If existing values are provided, it also checks against them for uniqueness.

    Args:
        columns (list[str]): List of column names that constitute the primary key.
        existing (list[tuple[Any, ...]]): Existing values to check against
            for uniqueness. Defaults to an empty list.
        label (str): Label of the checks in reporting
    """

    name: Literal["is_valid_primary_key"] = "is_valid_primary_key"

    columns: list[str]
    existing: list[tuple[Any, ...]] = field(default_factory=list)

    def validate(self, df: pd.DataFrame) -> pd.Series:
        """Check that the specified columns form a valid primary key
        (unique and non-null)."""
        is_unique = IsUnique(label=self.label, columns=self.columns)(df)
        is_not_null = IsNotNull(
            label=self.label, columns=self.columns, ignore_na=False
        )(df)
        # we could skip this check if self.existing is empty, but its cheap
        # anyways to we keep the behavior as in the pandera checks.
        is_externally_unique = IsIn(
            label=self.label,
            columns=self.columns,
            existing=self.existing,
            expected=False,
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
            *IsIn(
                label=self.label,
                columns=self.columns,
                existing=self.existing,
                expected=False,
            ).to_pandera(),
        ]
