"""Execution of a submission contract against a delivered bundle.

The counterpart to the spec models in this package: a `SubmissionContract`
describes how a bundle splits into per-variable datasets, and a
`SubmissionHandler` carries that description out against actual data.
"""

import pandas as pd

from crosscontract.submission.extraction import Target
from crosscontract.transformations import BaseTransformation

from .submission_contract import SubmissionContract


class SubmissionHandler:
    """Apply a submission contract's extraction instructions to a bundle.

    The handler answers one target at a time: `extract_target_data` selects the
    rows a target claims, `transform_target_data` applies that target's
    transformation profile and then its own transformations, and
    `get_target_data` composes the two. There is deliberately no method that runs
    every target, so whether a run aborts on the first failing target or collects
    every failure is the caller's decision rather than this class's.

    Like the extraction instructions it reads, the handler *names* target
    contracts and never resolves them, so it loads and runs with no platform
    connection.

    Attributes:
        contract (SubmissionContract): The contract describing the bundle and how
            it is split into targets.
        bundle (pd.DataFrame): A copy of the submitted data the instructions are
            applied to.
    """

    def __init__(self, contract: SubmissionContract, bundle: pd.DataFrame):
        """Bind a submission contract to the bundle it describes.

        The bundle is copied, so later changes to the frame handed in do not
        alter the handler's answers.

        Args:
            contract (SubmissionContract): The contract describing the bundle and
                how it is split into targets.
            bundle (pd.DataFrame): The submitted data, conforming to the
                contract's `tableschema`. Every column named by a target's
                `filters` must be present.
        """
        self.contract = contract
        self.bundle = bundle.copy()

    def _mask_target(self, target: Target) -> pd.Series:
        """Return a boolean mask selecting the bundle rows a target claims.

        A row is claimed when it satisfies every entry of the target's `filters`.
        Values are compared against the column's string form, so a filter on a
        typed column matches `str(value)`.

        Args:
            target (Target): The target whose filters select the rows.

        Returns:
            pd.Series: A boolean mask over the bundle's index.

        Raises:
            KeyError: If a column named by the target's `filters` is absent from
                the bundle.
        """
        mask = pd.Series(True, index=self.bundle.index)
        for column, value in target.filters.items():
            mask &= self.bundle[column].astype(str) == value
        return mask

    def get_target_data(self, target_name: str) -> pd.DataFrame:
        """Extract the target variable from the submission bundle and apply all
        transformations specified in the submission contract.

        Args:
            target_name (str): The name of the target to extract rows for.

        Returns:
            pd.DataFrame: A DataFrame containing the rows claimed by the target,
                after applying the target's transformation profile and transformations.

        Raises:
            KeyError: If no target with the given name exists, or if a column
                named by the target's `filters` is absent from the bundle.
        """
        df = self.extract_target_data(target_name)
        df = self.transform_target_data(df, target_name)
        return df

    def extract_target_data(self, target_name: str) -> pd.DataFrame:
        """Load the rows of a submission bundle that a target claims.

        Args:
            target_name (str): The name of the target to load rows for.

        Returns:
            pd.DataFrame: A DataFrame containing the rows claimed by the target.

        Raises:
            KeyError: If no target with the given name exists, or if a column
                named by the target's `filters` is absent from the bundle.
        """
        target = self.contract.extraction.get_target(target_name)
        return self.bundle[self._mask_target(target)]

    def transform_target_data(self, df: pd.DataFrame, target_name: str) -> pd.DataFrame:
        """Apply all transformations specified in the submission contract to the
        target variable.

        `df` is not checked against `target_name`: passing one target's rows
        under another target's name returns a plausible-looking wrong answer
        rather than raising. Pair them yourself, or use `get_target_data`.

        Args:
            df (pd.DataFrame): The DataFrame containing the rows claimed by the
                target. Not mutated; a new DataFrame is returned.
            target_name (str): The name of the target to transform.

        Returns:
            pd.DataFrame: A DataFrame containing the transformed rows of the
                target variable.

        Raises:
            KeyError: If no target with the given name exists.
        """
        target = self.contract.extraction.get_target(target_name)
        steps_to_apply: list[BaseTransformation] = []
        if target.transformation_profile:
            steps_to_apply.extend(
                self.contract.extraction.transformation_profiles[
                    target.transformation_profile
                ]
            )

        steps_to_apply.extend(target.transformations)
        df = df.copy()
        for step in steps_to_apply:
            df = step.apply(df)

        return df

    def unclaimed_rows(self) -> pd.DataFrame:
        """Return the rows of a submission bundle that no target claims.

        A row is claimed by a target when it satisfies every entry of that
        target's `filters`. Filter values are matched against the string form
        of the column, so a filter on a typed column compares against
        `str(value)` rather than against the typed value.

        Rows that no target claims are the rows extraction would silently drop.
        This method reports them and nothing more — whether an unclaimed row is
        an error or a warning is the caller's decision.

        Returns:
            pd.DataFrame: The unclaimed rows, keeping their index labels. Empty
                when every row is claimed.

        Raises:
            KeyError: If a column named by any target's `filters` is absent from
                the bundle.
        """

        claimed = pd.Series(False, index=self.bundle.index)
        for target in self.contract.extraction.targets:
            claimed |= self._mask_target(target)
        return self.bundle[~claimed]
