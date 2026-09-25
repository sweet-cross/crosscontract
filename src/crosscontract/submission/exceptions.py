"""The failures a submission raises: aggregate target validation and unclaimed rows."""

from collections.abc import Hashable
from typing import Any

import pandas as pd

from crosscontract.contracts.schema import SchemaValidationError


class TargetValidationError(Exception):
    """Collects the `SchemaValidationError`s raised while validating several targets.

    Raised once every target has been attempted, holding one entry per target
    whose extracted data failed validation against the contract it names.
    Distinct from `SchemaValidationError`, which wraps and parses a single
    pandera exception: this class holds a mapping of already-parsed failures
    and parses nothing itself.

    Attributes:
        errors (dict[str, SchemaValidationError]): The failing targets, keyed
            by target name, each holding its own validation failure. Note the
            divergence from `SchemaValidationError.errors`, which is a list of
            parsed failure rows: `to_list()` and `to_pandas()` mean the same
            thing on both classes, `errors` does not.
    """

    def __init__(self, errors: dict[str, SchemaValidationError]):
        """Initialize with the per-target validation failures.

        Args:
            errors (dict[str, SchemaValidationError]): The failing targets,
                keyed by target name.
        """
        self.errors = errors
        targets = ", ".join(sorted(errors))
        super().__init__(f"Target validation failed for: {targets}")

    def to_list(self, max_errors: int | None = None) -> list[dict[Hashable, Any]]:
        """Flatten every failing target's errors into a single list of rows.

        Each row is one entry from a target's
        `SchemaValidationError.to_list(max_errors)`, with a `target` key added
        naming which target it came from.

        With `max_errors`, each target's report is condensed on its own, as
        described on `SchemaValidationError.to_list`: repeated failing values merge
        into one row carrying a `count`, and each target keeps at most `max_errors`
        distinct failing values per check and column. With three failing targets,
        a column can therefore show up to three times `max_errors` values.

        Args:
            max_errors (int | None, optional): The maximum number of distinct
                failing values kept per check, column and target, at least 1.
                Defaults to `None`, which returns the full report.

        Returns:
            list[dict[Hashable, Any]]: The error rows across every failing target;
            one row per validation failure without `max_errors`.

        Raises:
            ValueError: If `max_errors` is smaller than 1.
        """
        return [
            {"target": target, **row}
            for target, error in self.errors.items()
            for row in error.to_list(max_errors=max_errors)
        ]

    def to_pandas(self, max_errors: int | None = None) -> pd.DataFrame:
        """Flatten every failing target's errors into a single DataFrame.

        Holds the rows of `to_list`, condensed in the same way when `max_errors`
        is given.

        Args:
            max_errors (int | None, optional): The maximum number of distinct
                failing values kept per check, column and target, at least 1.
                Defaults to `None`, which returns the full report.

        Returns:
            pd.DataFrame: The error rows across every failing target. Equivalent
            to `pd.DataFrame(self.to_list(max_errors))`.

        Raises:
            ValueError: If `max_errors` is smaller than 1.
        """
        return pd.DataFrame(self.to_list(max_errors=max_errors))


class UnclaimedRowsError(Exception):
    """Raised when a delivered bundle holds rows that no target claims.

    An unclaimed row is a row extraction would silently drop, so the error
    carries the rows themselves rather than a count. Note that `to_list()` and
    `to_pandas()` mean something different here than on `TargetValidationError`
    and `SchemaValidationError`: on those they render a failure report, here
    they render the offending bundle rows.

    Attributes:
        unclaimed_rows (pd.DataFrame): The bundle rows no target claims, as
            handed to the constructor and keeping their index labels.
    """

    def __init__(self, unclaimed_rows: pd.DataFrame):
        """Initialize with the unclaimed rows.

        Args:
            unclaimed_rows (pd.DataFrame): The rows that do not belong to any target.
        """
        self.unclaimed_rows = unclaimed_rows
        super().__init__(
            f"{len(unclaimed_rows)} unclaimed rows found. Use the "
            "`to_list()` or `to_pandas()` methods to inspect them."
        )

    def to_list(self) -> list[dict[Hashable, Any]]:
        """Return the unclaimed rows as a list of dictionaries.

        Returns:
            list[dict[Hashable, Any]]: The unclaimed rows.
        """
        return self.unclaimed_rows.to_dict(orient="records")

    def to_pandas(self) -> pd.DataFrame:
        """Return the unclaimed rows as a DataFrame.

        Returns:
            pd.DataFrame: The unclaimed rows.
        """
        return pd.DataFrame(self.unclaimed_rows)
