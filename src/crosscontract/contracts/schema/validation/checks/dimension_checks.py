from abc import ABC
from typing import Any, Literal

import pandas as pd
import pandera.pandas as pa
from pydantic import Field

from .abstract_base import BaseCheck


class DimensionCheck(BaseCheck, ABC):
    """Base for the checks over a dimension hierarchy.

    A dimension is described by three columns — the identifier of an entry, the
    identifier of its parent, and its level in the hierarchy. Their names are
    configurable so a check can run against a frame that spells them differently.
    """

    id_col: str = Field(
        default="id",
        description="The column holding the identifier of an entry.",
    )
    parent_id_col: str = Field(
        default="parent_id",
        description="The column holding the identifier of the parent entry.",
    )
    level_col: str = Field(
        default="level",
        description="The column holding the level of an entry in the hierarchy.",
    )

    @property
    def _column_kwargs(self) -> dict[str, Any]:
        """Returns:
        dict[str, Any]: The configured column names, for building another
            dimension check over the same frame.
        """
        return {
            "id_col": self.id_col,
            "parent_id_col": self.parent_id_col,
            "level_col": self.level_col,
        }


class RootElementHasNoParent(DimensionCheck):
    """The root level of the dimension hierarchy should not have a parent_id."""

    name: Literal["root_element_has_no_parent"] = "root_element_has_no_parent"

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        is_root = df[self.level_col] == 0
        has_parent = df[self.parent_id_col].notna() & (df[self.parent_id_col] != "")
        return ~is_root | ~has_parent

    def failure_message(self) -> str:
        return (
            f"Root level violation in '{self.label}': Root level should not "
            f"have a parent_id."
        )


class NonRootElementHasParent(DimensionCheck):
    """Each sub-level must have a parent_id."""

    name: Literal["non_root_element_has_parent"] = "non_root_element_has_parent"

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        needs_parent = df[self.level_col] > 0
        has_parent = df[self.parent_id_col].notna() & (df[self.parent_id_col] != "")
        return ~needs_parent | has_parent

    def failure_message(self) -> str:
        return (
            f"Non-root level violation in '{self.label}': Each sub-level must have"
            " a parent_id."
        )


class ParentHasCorrectLevel(DimensionCheck):
    """Each sub-level must have a parent that has a level equal to the current
    level minus one."""

    name: Literal["parent_has_correct_level"] = "parent_has_correct_level"

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        """Check that parent of the non-root rows exist in the level above.

        Args:
            df (pd.DataFrame): The dimension table to validate.

        Returns:
            pd.Series: A boolean series indicating which rows pass the check.
        """
        is_root = df[self.level_col] == 0

        # add the level of the parent_id
        id_to_level = df.set_index(self.id_col)[self.level_col]
        parent_levels = df[self.parent_id_col].map(id_to_level)

        result = pd.Series(True, index=df.index)
        # parent level must be the own level minus one for non-root rows. A
        # parent_id that matches no entry maps to NA, which counts as a failure.
        result.loc[~is_root] = (
            parent_levels[~is_root] == df.loc[~is_root, self.level_col] - 1
        ).to_numpy(dtype=bool, na_value=False)
        return result

    def failure_message(self) -> str:
        return (
            f"Parent level violation in '{self.label}': Each sub-level must "
            "have a parent that has a level equal to the current level minus one."
        )


class EachLevelHasOther(DimensionCheck):
    """Each dimension level must have at least one other element at the same level.

    The logic is that the root has an element `other` and the remaining levels
    must have `<parent_id>_other`
    """

    name: Literal["each_dimension_level_has_other"] = "each_dimension_level_has_other"

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        is_root = df[self.level_col] == 0

        # Root level: must have id == "other"
        root_ok = df.loc[is_root, self.id_col].eq("other").any()

        # Non-root: each row's parent must have a sibling "<parent_id>_other"
        # only done if there are any non-root rows
        result = pd.Series(True, index=df.index)
        result.loc[is_root] = bool(root_ok)
        if not is_root.all():
            non_root = df[~is_root]
            expected_other = non_root[self.parent_id_col].astype(str) + "_other"
            parent_has_other = non_root.groupby(self.parent_id_col)[
                self.id_col
            ].transform(
                lambda ids: expected_other.loc[ids.index].isin(ids.values).any()
            )
            result.loc[~is_root] = parent_has_other.to_numpy(dtype=bool, na_value=False)

        return result

    def failure_message(self) -> str:
        return (
            f"Each dimension level violation in '{self.label}': Each level must "
            "have at least one other element. For sub-levels, this means each "
            "parent must have a child with the '<parent_id>_other' suffix"
            "and the root level must have an element with id 'other'."
        )


class IsValidCrossDimension(DimensionCheck):
    """Check to be a valid CrossDimensions that includes.

    The checks include:
        1. Root level entries must not have a parent_id.
        2. Each sub-level must have a parent_id pointing to the level above.
        3. Each sub-level must have a parent_id.
        4. The root level of the dimension hierarchy must have an entry with id "other".
        Each sub-level must have a sibling entry with id "other_<parent_id>" to
        capture uncategorized entries at that level.
    """

    name: Literal["is_valid_cross_dimension"] = "is_valid_cross_dimension"

    @property
    def _sub_checks(self) -> list[DimensionCheck]:
        """Returns:
        list[DimensionCheck]: The rules this check is made of, built in one place
            so the predicate and the pandera conversion cannot drift apart.
        """
        return [
            RootElementHasNoParent(label=self.label, **self._column_kwargs),
            NonRootElementHasParent(label=self.label, **self._column_kwargs),
            EachLevelHasOther(label=self.label, **self._column_kwargs),
            ParentHasCorrectLevel(label=self.label, **self._column_kwargs),
        ]

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        """Check if the DataFrame represents a valid cross-dimension hierarchy.

        That includes:
        1. Root level entries must not have a parent_id.
        2. Each sub-level must have a parent_id pointing to the level above.
        3. Each sub-level must have a parent_id.
        4. The root level of the dimension hierarchy must have an entry with id "other".
        Each sub-level must have a sibling entry with id "other_<parent_id>" to
        capture uncategorized entries at that level.

        Args:
            df (pd.DataFrame): The DataFrame representing the cross-dimension hierarchy.

        Returns:
            pd.Series: A boolean Series indicating whether each row satisfies
                the cross-dimension hierarchy rules.
        """
        result = pd.Series(True, index=df.index)
        for check in self._sub_checks:
            result &= check(df)
        return result

    def failure_message(self) -> str:
        """Return the failure message for the cross-dimension check."""
        return (
            f"Hierarchy violation in '{self.label}': The entries do not form a "
            "valid dimension hierarchy."
        )

    def to_pandera(self) -> list[pa.Check]:
        """Unpack the individual rules into pandera checks, so a report names the
        rule that broke."""
        return [
            pandera_check
            for check in self._sub_checks
            for pandera_check in check.to_pandera()
        ]
