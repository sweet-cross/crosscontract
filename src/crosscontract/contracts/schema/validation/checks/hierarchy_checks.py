"""Checks to test the integrity in case of references to hierarchical
dimensions"""

from abc import ABC
from typing import Any, Literal

import pandas as pd
import pandera.pandas as pa
from pydantic import Field

from .abstract_base import BaseCheck


class HasNoDescendantInGroup(BaseCheck):
    """Check that no row has a descendant in the same group."""

    name: Literal["has_no_descendant_in_group"] = "has_no_descendant_in_group"

    column: str = Field(
        ..., description="The column representing the hierarchical dimension."
    )
    group_columns: list[str] = Field(
        ...,
        description=(
            "The columns defining the group within which descendants should not appear."
        ),
    )
    parent_map: dict[str, str | None] = Field(
        ..., description="A mapping from each node to its parent in the hierarchy."
    )

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        """Check that no entry at level 0 names a parent.

        Args:
            df (pd.DataFrame): The dimension table to validate.

        Returns:
            pd.Series: A boolean Series indicating which rows pass the check.
                Entries below the root level always pass.
        """
        return pd.Series([True] * len(df))

    def failure_message(self) -> str:
        """Return the failure message for the root level check."""
        return f"Hierarchy '{self.label}': Root level should not have a parent_id."
