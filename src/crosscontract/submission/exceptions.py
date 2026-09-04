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

    def to_list(self) -> list[dict[Hashable, Any]]:
        """Flatten every failing target's errors into a single list of rows.

        Each row is one entry from a target's `SchemaValidationError.to_list()`,
        with a `target` key added naming which target it came from.

        Returns:
            list[dict[Hashable, Any]]: One row per validation failure, across
            every failing target.
        """
        return [
            {"target": target, **row}
            for target, error in self.errors.items()
            for row in error.to_list()
        ]

    def to_pandas(self) -> pd.DataFrame:
        """Flatten every failing target's errors into a single DataFrame.

        Returns:
            pd.DataFrame: One row per validation failure, across every failing
            target. Equivalent to `pd.DataFrame(self.to_list())`.
        """
        return pd.DataFrame(self.to_list())


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
