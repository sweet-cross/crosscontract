"""Helpers shared by the check classes."""

from typing import Any


def validate_existing_length_match(
    columns: list[str], existing: list[tuple[Any, ...]]
) -> None:
    """Ensure every existing value holds one entry per checked column.

    A value that is not as wide as the key it is compared against matches
    nothing, so the check carrying it would silently pass or fail every row
    rather than report the mistake.

    Args:
        columns (list[str]): The columns the check applies to.
        existing (list[tuple[Any, ...]]): The existing values to compare against.

    Raises:
        ValueError: If an existing value does not have as many entries as there
            are columns.
    """
    mismatched = [t for t in existing if len(t) != len(columns)]
    if mismatched:
        raise ValueError(
            f"Existing values must have {len(columns)} entries to match "
            f"columns {columns}, but got {mismatched}."
        )
