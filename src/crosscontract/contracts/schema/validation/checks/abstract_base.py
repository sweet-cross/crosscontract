"""Abstract base class for validation checks."""

from abc import ABC, abstractmethod

import pandas as pd
import pandera.pandas as pa
from pydantic import BaseModel, ConfigDict, Field


class BaseCheck(BaseModel, ABC):
    """Base class for validation checks. Each check implements a `validate` method
    that takes a dataframe as input.

    A check carries two identities. `name` is the mechanical identity of the check
    class, shared by every instance of it, and serves as the discriminator when
    checks are read from a specification. `key` is the identity of the instance:
    the mechanic together with whatever the check applies to.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        description=(
            "The name of the check. This has to be unique among all check classes "
            "and serves as discriminator."
        ),
    )
    label: str = Field(
        description="The label or column name the check applies to.",
    )

    ignore_na: bool = Field(
        default=True,
        description=(
            "Whether to ignore NA values in the pandera check logic. Defaults to "
            "`True`, the pandera default."
        ),
    )
    expected: bool = Field(
        default=True,
        description="The expected outcome of the check.",
    )

    @property
    def key(self) -> str:
        """Returns:
        str: The identity of this check instance. Two checks built at different
            sites carry the same key when they express the same rule.
        """
        return self.name

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
                name=self.key,
                error=self.failure_message(),
                ignore_na=self.ignore_na,
            )
        ]
