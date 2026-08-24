import pandas as pd

from crosscontract.submission.extraction import Target

from .submission_contract import SubmissionContract


class SubmissionHandler:
    def __init__(self, specs: SubmissionContract, df: pd.DataFrame):
        self.specs = specs
        self.bundle = df

    def _mask_target(self, target: Target) -> pd.Series:
        """Return a boolean mask selecting the bundle rows a target claims.

        A row is claimed when it satisfies every entry of the target's `filters`.
        Values are compared against the column's string form, so a filter on a
        typed column matches `str(value)`.

        Args:
            target (Target): The target whose filters select the rows.

        Returns:
            pd.Series: A boolean mask over the bundle's index.
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
            pd.DataFrame: A DataFrame containing the rows claimed by the target.
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
        """
        target = self.specs.extraction.get_target(target_name)
        return self.bundle[self._mask_target(target)]

    def transform_target_data(self, df: pd.DataFrame, target_name: str) -> pd.DataFrame:
        """Apply all transformations specified in the submission contract to the
        target variable.

        Args:
            df (pd.DataFrame): The DataFrame containing the rows claimed by the
                target.
            target_name (str): The name of the target to transform.

        Returns:
            pd.DataFrame: A DataFrame containing the transformed rows of the
                target variable.
        """
        # apply transformation profile and then transformations

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
        """

        claimed = pd.Series(False, index=self.bundle.index)
        for target in self.specs.extraction.targets:
            claimed |= self._mask_target(target)
        return self.bundle[~claimed]
