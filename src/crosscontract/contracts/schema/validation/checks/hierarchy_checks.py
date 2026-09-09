"""Checks on data that references a hierarchical dimension."""

from typing import Any, Literal

import pandas as pd
from pydantic import Field

from .abstract_base import BaseCheck


class HasNoDescendantInGroup(BaseCheck):
    """Check that the dimension members reported within one group form an
    antichain.

    A group is the set of rows sharing the same values in `group_columns`.
    Within one group, no member in `column` may be a proper ancestor of another
    member present: a row for `ch` alongside a row for `ch_ag` counts `ch_ag`
    twice when the column is summed.

    The failing row is the aggregate one — `ch` fails because `ch_ag` is
    present — because that is the row to act on. The remedy is to remove it, or
    to move the detail into it.

    Two consequences for a caller:

    - Only the frame under validation is inspected. A violation split across two
      uploads, with the aggregate already stored, is not caught here.
    - A member missing from `parent_map` passes, as does a null member. An
      unknown member is `IsSubsetOf`'s to report.
    """

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

    def _ancestors(self, members: pd.Series) -> dict[str, list[str]]:
        """Map every member the data reports to its proper ancestors.

        Each distinct member is walked once, however many rows report it. A
        member missing from `parent_map` gets an empty list, and an empty string
        ends a chain just as a null does.

        Args:
            members (pd.Series): The dimension members the data reports.

        Returns:
            dict[str, list[str]]: Each member mapped to its proper ancestors,
                nearest first.
        """
        ancestors: dict[str, list[str]] = {}
        for node in members.dropna().unique():
            chain: list[str] = []
            # `seen` stops a broken parent map that loops back on itself, and
            # keeps a member out of its own chain.
            seen = {node}
            parent = self.parent_map.get(node)
            while parent and parent not in seen:
                chain.append(parent)
                seen.add(parent)
                parent = self.parent_map.get(parent)
            ancestors[node] = chain
        return ancestors

    def _row_keys(self, df: pd.DataFrame) -> list[tuple[tuple[Any, ...], Any]]:
        """Pair every row with its group, in the frame's own order.

        A group key is the row's values in `group_columns` as a tuple, so two
        rows share a group when those values match. Nulls are normalised to
        `None` first: the group columns come from the primary key and so for a
        ValueVariable are never null, but the primary key check is opt-in, and
        two nan values never compare equal, which would split rows that belong
        in one group.

        Args:
            df (pd.DataFrame): The data to validate.

        Returns:
            list[tuple[tuple[Any, ...], Any]]: One (group key, member) pair per
                row.
        """
        groups = df[self.group_columns].astype(object)
        groups = groups.where(groups.notna(), None)
        return list(
            zip(groups.itertuples(index=False, name=None), df[self.column], strict=True)
        )

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        """Check that no row reports a member whose descendant is in its group.

        Args:
            df (pd.DataFrame): The data to validate.

        Returns:
            pd.Series: A boolean Series indicating which rows pass the check.
        """
        # A parent map only goes upwards, so the check works upwards too. Each
        # row marks the aggregates it is part of as covered, within its own
        # group. A row fails if its own member is already marked: something
        # below it reports the same quantity, and summing the column would
        # count that quantity twice.
        #
        # With group columns (model, scenario, year) and 'ch_ag' a child of
        # 'ch':
        #
        #     model scenario year  region  value
        #     m1    A        2030  ch      100     <- fails
        #     m1    A        2030  ch_ag    30
        #     m2    A        2030  ch_ag    30
        #
        # Each 'ch_ag' row marks 'ch' in its own group, so covered holds
        # ((m1, A, 2030), 'ch') and ((m2, A, 2030), 'ch'). Row 1 finds its own
        # pair there and fails: its 100 already contains the 30 below it. Row 2
        # passes, nothing is below 'ch_ag'. Row 3 passes and never touches m1's
        # group, which is why two models may report at different granularities.
        ancestors = self._ancestors(df[self.column])
        rows = self._row_keys(df)

        # Mark what each group already covers: the ancestors that must not
        # appear in it, because a descendant of theirs is already there.
        covered = {
            (group_key, ancestor)
            for group_key, member in rows
            for ancestor in ancestors.get(member, [])
        }

        # A row fails if it is already covered: a descendant of its member is
        # in the same group. A null member is in no branch, so nothing covers
        # it and it always passes.
        return pd.Series(
            [
                pd.isna(member) or (group_key, member) not in covered
                for group_key, member in rows
            ],
            index=df.index,
            dtype=bool,
        )

    def failure_message(self) -> str:
        """Return the failure message for the granularity check."""
        columns = ", ".join([self.column, *self.group_columns])
        return (
            f"Columns '{columns}' in check '{self.label}' report an aggregate "
            "member while a row for one of its descendants is present in the "
            "same group. Remove the aggregate row, or move the detail into it."
        )
