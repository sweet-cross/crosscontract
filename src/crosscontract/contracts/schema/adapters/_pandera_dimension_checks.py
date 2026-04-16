from typing import TYPE_CHECKING

import pandas as pd
import pandera.pandas as pa

if TYPE_CHECKING:  # pragma: no cover
    from crosscontract.contracts.schema.schema import TableSchema


def get_dimension_checks(schema: "TableSchema") -> list[pa.Check]:
    """Returns a list of pandera checks to validate the consistency of a
    dimension hierarchy.

    The checks include:
    1. Root level entries should not have a parent_id.
    2. Each sub-level needs parent_id pointing to level above.
    3. Each sub-level needs a parent_id.
    4. The root level of the dimension hierarchy should have an entry with id "other".
       Each sub-level should have a sibling entry with id "<parent_id>_other" to
       capture uncategorized entries at that level.

    Args:
        schema: The TableSchema of the dimension table to generate checks for.

    Returns:
        A list of pandera Check objects to validate the dimension hierarchy.
    """
    return [
        pa.Check(
            _check_root_no_parent,
            name="DimensionCheck: Root level entries should not have a parent_id",
        ),
        pa.Check(
            _check_parent_level,
            name=(
                "DimensionCheck: Each sub-level needs parent_id pointing to level above"
            ),
        ),
        pa.Check(
            _check_parent_id_required,
            name="DimensionCheck: Each sub-level needs a parent_id",
        ),
        pa.Check(
            _check_other_entries,
            name="DimensionCheck: Other entry existence for each level",
        ),
    ]


def _check_parent_level(df: pd.DataFrame) -> pd.Series:
    """A row at level N (N > 0) must reference a parent at level N-1."""
    is_root = df["level"] == 0

    # Build id → level lookup
    id_to_level = df.set_index("id")["level"]

    # For non-root rows, resolve the parent's level
    parent_levels = df["parent_id"].map(id_to_level)

    # Valid if parent_level == own_level - 1
    result = pd.Series(True, index=df.index)
    result.loc[~is_root] = (
        parent_levels[~is_root] == df.loc[~is_root, "level"] - 1
    ).to_numpy(dtype=bool, na_value=False)
    return result


def _check_root_no_parent(df: pd.DataFrame) -> pd.Series:
    """The root level of the dimension hierarchy should not have a parent_id.

    Args:
        df: The dimension DataFrame to check.

    Returns:
        A boolean Series where True indicates rows that pass the check."""
    is_root = df["level"] == 0
    has_parent = df["parent_id"].notna() & (df["parent_id"] != "")
    return ~is_root | ~has_parent


def _check_parent_id_required(df: pd.DataFrame) -> pd.Series:
    """Each sub-level needs a parent_id to keep the dimension hierarchy
    consistent.

    Args:
        df: The dimension DataFrame to check.

    Returns:
        A boolean Series where True indicates rows that pass the check.
    """
    needs_parent = df["level"] > 0
    has_parent = df["parent_id"].notna() & (df["parent_id"] != "")
    return ~needs_parent | has_parent


def _check_other_entries(df: pd.DataFrame) -> pd.Series:
    """The root level of the dimension hierarchy should have an entry with id "other".
    Each sub-level should have a sibling entry with id "<parent_id>_other" to
    capture uncategorized entries at that level.  This ensures that the dimension
    can be used for aggregation without losing data due to missing parent-child links.

    Args:
        df: The dimension DataFrame to check.

    Returns:
        A boolean Series where True indicates rows that pass the check.
    """
    is_root = df["level"] == 0

    # Root level: must have id == "other"
    root_ok = df.loc[is_root, "id"].eq("other").any()

    # Non-root: each row's parent must have a sibling "other_<parent_id>"
    # only done if there are any non-root rows
    result = pd.Series(True, index=df.index)
    result.loc[is_root] = bool(root_ok)
    if not is_root.all():
        non_root = df[~is_root]
        expected_other = non_root["parent_id"].astype(str) + "_other"
        parent_has_other = non_root.groupby("parent_id")["id"].transform(
            lambda ids: expected_other.loc[ids.index].isin(ids.values).any()
        )
        result.loc[~is_root] = parent_has_other.to_numpy(dtype=bool, na_value=False)
    return result
