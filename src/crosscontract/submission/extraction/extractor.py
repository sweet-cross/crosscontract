import pandas as pd

from .. import SubmissionContract


class SubmissionExtractor:
    def __init__(self, specs: SubmissionContract, df: pd.DataFrame):
        self.specs = specs
        self.data = df

    def get_target_data(self, target_name: str) -> pd.DataFrame:
        """Extract the target variable from the submission bundle and apply all
        transformations specified in the submission contract.

        Args:
            target_name (str): The name of the target to extract rows for.

        Returns:
            pd.DataFrame: A DataFrame containing the rows claimed by the target.
        """
        df = self.load_target(target_name)
        df = self.transform_target(df, target_name)
        return df

    def extract_target_data(self, target_name: str) -> pd.DataFrame:
        """Load the rows of a submission bundle that a target claims.

        Args:
            target_name (str): The name of the target to load rows for.

        Returns:
            pd.DataFrame: A DataFrame containing the rows claimed by the target.
        """
        # extract the bare target from the submission bundle using the filters

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
