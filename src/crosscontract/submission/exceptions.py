"""Aggregate failures from validating a submission's targets."""

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
            by target name, each holding its own validation failure.
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
