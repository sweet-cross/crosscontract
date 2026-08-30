"""Abstract base class for validation checks."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

import pandas as pd
import pandera as pa


@dataclass(kw_only=True)
class BaseCheck(ABC):
    """Base class for validation checks. Each check implements a __call__ method
    that takes a dataframe as input.

    Args:
        name (ClassVar[str]): The name of the check. This has to be unique among
            all classes and can serve as discriminator.
        label (str): The label or column name the check applies to.
        ignore_na (bool, optional): Whether to ignore NA values in the pandera
            check logic.
            Defaults to True (pandera default).
        expected (bool, optional): The expected outcome of the check.
            Defaults to True.
    """

    name: ClassVar[str]
    label: str

    ignore_na: bool = True
    expected: bool = True

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        """The Template Method: manages the execution and applies 'expected'."""
        raw_result = self.validate(df)
        return raw_result == self.expected

    @abstractmethod
    def validate(self, df: pd.DataFrame) -> pd.Series:
        """Implement the core validation logic here. Return a boolean Series
        indicating which rows pass the check."""
        ...

    def failure_message(self) -> str:
        """String to be used in error messages."""
        return f"Check '{self.name}' with label '{self.label}' failed."

    def to_pandera(self) -> list[pa.Check]:
        """Convert this check to a pandera Check."""
        return [
            pa.Check(
                self,
                name=self.name,
                error=self.failure_message(),
                ignore_na=self.ignore_na,
            )
        ]
