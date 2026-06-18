from abc import ABC, abstractmethod

import pandas as pd
from pydantic import BaseModel, ConfigDict


class BaseTransformation(BaseModel, ABC):
    """Base class for declarative transformation specs.

    A transformation spec is a typed, declarative description of a single
    operation applied to a DataFrame. Concrete subclasses are discriminated by
    their `type` field and delegate `apply` to the matching pure function in
    this module.

    Subclasses set `extra="forbid"`-backed explicit fields so that the spec
    documents and validates the exact keys a user may provide (e.g. in YAML).
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    @abstractmethod
    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply the transformation to a DataFrame.

        The input DataFrame is not mutated; a new DataFrame is returned.

        Args:
            df (pd.DataFrame): The DataFrame to transform.

        Returns:
            pd.DataFrame: A new, transformed DataFrame.
        """
        ...
