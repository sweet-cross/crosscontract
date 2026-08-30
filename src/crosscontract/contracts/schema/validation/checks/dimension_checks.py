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
    """An entry at the root level must not name a parent.

    Level 0 is the top of the hierarchy, so there is nothing for it to point at.
    An empty string counts as no parent, the same as a null.
    """

    name: Literal["root_element_has_no_parent"] = "root_element_has_no_parent"

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        """Check that no entry at level 0 names a parent.

        Args:
            df (pd.DataFrame): The dimension table to validate.

        Returns:
            pd.Series: A boolean Series indicating which rows pass the check.
                Entries below the root level always pass.
        """
        is_root = df[self.level_col] == 0
        has_parent = df[self.parent_id_col].notna() & (df[self.parent_id_col] != "")
        return ~is_root | ~has_parent

    def failure_message(self) -> str:
        """Return the failure message for the root level check."""
        return (
            f"Root level violation in '{self.label}': Root level should not "
            f"have a parent_id."
        )


class NonRootElementHasParent(DimensionCheck):
    """An entry below the root level must name a parent.

    Without one it is detached from the hierarchy and cannot be aggregated into
    any level above it. An empty string counts as no parent, the same as a null.
    """

    name: Literal["non_root_element_has_parent"] = "non_root_element_has_parent"

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        """Check that every entry below level 0 names a parent.

        Args:
            df (pd.DataFrame): The dimension table to validate.

        Returns:
            pd.Series: A boolean Series indicating which rows pass the check.
                Entries at the root level always pass.
        """
        needs_parent = df[self.level_col] > 0
        has_parent = df[self.parent_id_col].notna() & (df[self.parent_id_col] != "")
        return ~needs_parent | has_parent

    def failure_message(self) -> str:
        """Return the failure message for the missing parent check."""
        return (
            f"Non-root level violation in '{self.label}': Each sub-level must have"
            " a parent_id."
        )


class ParentHasCorrectLevel(DimensionCheck):
    """An entry at level N must name a parent that sits at level N-1.

    The hierarchy therefore has no gaps: a level is reached from the one directly
    above it, never from further up and never sideways. A parent that matches no
    entry at all fails for the same reason.
    """

    name: Literal["parent_has_correct_level"] = "parent_has_correct_level"

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        """Check that parent of the non-root rows exist in the level above.

        Args:
            df (pd.DataFrame): The dimension table to validate.

        Returns:
            pd.Series: A boolean series indicating which rows pass the check.
        """
        is_root = df[self.level_col] == 0

        # add the level of the parent_id. A duplicated id would make the lookup
        # unbuildable, so only the first is kept: the duplicate is a defect this
        # rule does not own — the id's own uniqueness constraint reports it — and
        # answering from an arbitrary one of them beats failing to answer at all.
        id_to_level = df.drop_duplicates(subset=[self.id_col]).set_index(self.id_col)[
            self.level_col
        ]
        parent_levels = df[self.parent_id_col].map(id_to_level)

        result = pd.Series(True, index=df.index)
        # parent level must be the own level minus one for non-root rows. A
        # parent_id that matches no entry maps to NA, which counts as a failure.
        result.loc[~is_root] = (
            parent_levels[~is_root] == df.loc[~is_root, self.level_col] - 1
        ).to_numpy(dtype=bool, na_value=False)
        return result

    def failure_message(self) -> str:
        """Return the failure message for the parent level check."""
        return (
            f"Parent level violation in '{self.label}': Each sub-level must "
            "have a parent that has a level equal to the current level minus one."
        )


class EachLevelHasOther(DimensionCheck):
    """Every sibling group must carry a catch-all entry for what it does not name.

    A sibling group is the set of entries sharing one parent, and the root
    entries form a group of their own. The root group must hold an entry with the
    id `other`; every group below it must hold one with the id
    `<parent_id>_other`. Those entries are where rows belonging to no named
    sibling are aggregated, which is what keeps a sum over any level equal to a
    sum over the level above it.

    Note that the grouping is by **parent**, not by level: two parents at the
    same level are judged separately, and one may pass while the other fails.

    Unlike the rules that read a parent, this one groups on the raw value, so an
    empty string is a parent id like any other and its group is asked for
    `_other`. `RootElementHasNoParent` and `NonRootElementHasParent` instead read
    it as no parent at all.
    """

    name: Literal["each_dimension_level_has_other"] = "each_dimension_level_has_other"

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        """Check that every sibling group holds its own catch-all entry.

        Asked of a single row, the rule is: which sibling group am I in, and does
        that group contain the catch-all? A parent with no children is asked
        nothing — there is no group, so there is no entry to require.

        A group missing its catch-all fails every member of that group, not the
        parent, because the entry is missing from the group.

        A row below the root that names no parent is in no sibling group, so this
        rule is not the one that judges it — `NonRootElementHasParent` owns a
        missing parent and reports it. It is nonetheless marked as failing here
        whenever another non-root row does name a parent, because the grouping
        drops the null key and returns no answer for that row. Only when no
        non-root row names a parent at all is there no grouping, and the row
        keeps its initial pass.

        Args:
            df (pd.DataFrame): The dimension table to validate.

        Returns:
            pd.Series: A boolean Series indicating which rows pass the check.
        """
        is_root = df[self.level_col] == 0

        # Root level: must have id == "other"
        root_ok = df.loc[is_root, self.id_col].eq("other").any()

        # Non-root: each row's group must hold a sibling "<parent_id>_other"
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
            # groupby drops the null parent key, so a row with no parent comes
            # back without an answer and is written as a failure. Its missing
            # parent is NonRootElementHasParent's to report.
            result.loc[parent_has_other.index] = parent_has_other.to_numpy(
                dtype=bool, na_value=False
            )

        return result

    def failure_message(self) -> str:
        """Return the failure message for the catch-all entry check."""
        return (
            f"Each dimension level violation in '{self.label}': Each level must "
            "have at least one other element. For sub-levels, this means each "
            "parent must have a child with the '<parent_id>_other' suffix "
            "and the root level must have an element with id 'other'."
        )


class IsValidCrossDimension(DimensionCheck):
    """The entries form a valid CROSS dimension hierarchy.

    Four rules taken together:

    1. An entry at the root level must not name a parent.
    2. An entry below the root level must name a parent.
    3. That parent must sit exactly one level above.
    4. Every level must carry a catch-all entry — `other` at the root, and
       `<parent_id>_other` under every parent below it.

    Together they guarantee the property the dimension exists for: every entry
    reaches the root through exactly one chain of parents, and nothing is lost on
    the way up, so summing any level equals summing the level above it.
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
        """Check that the DataFrame forms a valid CROSS dimension hierarchy.

        A row passes only when it passes all four rules, so one row can be
        reported for more than one reason.

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
        return (  # pragma: no cover
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
