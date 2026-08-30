from typing import Literal

import pandas as pd
import pandera.pandas as pa

from .abstract_base import BaseCheck


class RootElementHasNoParent(BaseCheck):
    """The root level of the dimension hierarchy should not have a parent_id."""

    name: Literal["root_element_has_no_parent"] = "root_element_has_no_parent"

    id_col: str = "id"
    parent_id_col: str = "parent_id"
    level_col: str = "level"

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        is_root = df[self.level_col] == 0
        has_parent = df[self.parent_id_col].notna() & (df[self.parent_id_col] != "")
        return ~is_root | ~has_parent

    def failure_message(self) -> str:
        return (
            f"Root level violation in '{self.label}': Root level should not "
            f"have a parent_id."
        )


class NonRootElementHasParent(BaseCheck):
    """Each sub-level must have a parent_id."""

    name: Literal["non_root_element_has_parent"] = "non_root_element_has_parent"

    id_col: str = "id"
    parent_id_col: str = "parent_id"
    level_col: str = "level"

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        needs_parent = df[self.level_col] > 0
        has_parent = df[self.parent_id_col].notna() & (df[self.parent_id_col] != "")
        return ~needs_parent | has_parent

    def failure_message(self) -> str:
        return (
            f"Non-root level violation in '{self.label}': Each sub-level must have"
            " a parent_id."
        )


class ParentHasCorrectLevel(BaseCheck):
    """Each sub-level must have a parent that has a level equal to the current
    level minus one."""

    name: Literal["parent_has_correct_level"] = "parent_has_correct_level"

    id_col: str = "id"
    parent_id_col: str = "parent_id"
    level_col: str = "level"

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        """Check that parent of the non-root rows exist in the level above.

        Args:
            df (pd.DataFrame): The dimension table to validate.

        Returns:
            pd.Series: A boolean series indicating which rows pass the check.
        """
        is_root = df[self.level_col] == 0

        # add the level of the parent_id
        id_to_level = df.set_index("id")["level"]
        parent_levels = df["parent_id"].map(id_to_level)

        result = pd.Series(True, index=df.index)
        # parent level must be the own level minus one for non-root rows
        result.loc[~is_root] = parent_levels[~is_root] == df.loc[~is_root, "level"] - 1
        return result

    def failure_message(self) -> str:
        return (
            f"Parent level violation in '{self.label}': Each sub-level must "
            "have a parent that has a level equal to the current level minus one."
        )


class EachLevelHasOther(BaseCheck):
    """Each dimension level must have at least one other element at the same level.

    The logic is that the root has an element `other` and the remaining levels
    must have `<parent_id>_other`
    """

    name: Literal["each_dimension_level_has_other"] = "each_dimension_level_has_other"

    id_col: str = "id"
    parent_id_col: str = "parent_id"
    level_col: str = "level"

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


class IsValidCrossDimension(BaseCheck):
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

    id_col: str = "id"
    parent_id_col: str = "parent_id"
    level_col: str = "level"

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
        root_has_no_parent = RootElementHasNoParent(
            label=self.label,
            id_col=self.id_col,
            parent_id_col=self.parent_id_col,
            level_col=self.level_col,
        )(df)
        sub_level_has_parent = NonRootElementHasParent(
            label=self.label,
            id_col=self.id_col,
            parent_id_col=self.parent_id_col,
            level_col=self.level_col,
        )(df)

        has_other_element = EachLevelHasOther(
            label=self.label,
            id_col=self.id_col,
            parent_id_col=self.parent_id_col,
            level_col=self.level_col,
        )(df)

        parent_has_correct_level = ParentHasCorrectLevel(
            label=self.label,
            id_col=self.id_col,
            parent_id_col=self.parent_id_col,
            level_col=self.level_col,
        )(df)

        return (
            root_has_no_parent
            & sub_level_has_parent
            & has_other_element
            & parent_has_correct_level
        )

    def failure_message(self) -> str:
        return (
            f"Hierarchy violation in '{self.label}': Parent level must be exactly N-1."
        )

    def to_pandera(self) -> list[pa.Check]:
        """Provide the pandera checks corresponding to this cross-dimension
        validation."""
        return [
            pa.Check(
                lambda df: RootElementHasNoParent(
                    label=self.label,
                    id_col=self.id_col,
                    parent_id_col=self.parent_id_col,
                    level_col=self.level_col,
                )(df)
            ),
            pa.Check(
                lambda df: NonRootElementHasParent(
                    label=self.label,
                    id_col=self.id_col,
                    parent_id_col=self.parent_id_col,
                    level_col=self.level_col,
                )(df)
            ),
            pa.Check(
                lambda df: EachLevelHasOther(
                    label=self.label,
                    id_col=self.id_col,
                    parent_id_col=self.parent_id_col,
                    level_col=self.level_col,
                )(df)
            ),
            pa.Check(
                lambda df: ParentHasCorrectLevel(
                    label=self.label,
                    id_col=self.id_col,
                    parent_id_col=self.parent_id_col,
                    level_col=self.level_col,
                )(df)
            ),
        ]
