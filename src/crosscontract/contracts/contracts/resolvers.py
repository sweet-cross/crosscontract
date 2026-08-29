from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import pandas as pd

if TYPE_CHECKING:  # pragma: no cover
    from .base_contract import BaseContract


@runtime_checkable
class ContractResolver(Protocol):
    @abstractmethod
    def resolve(self, name: str) -> "BaseContract | None":
        """Return the contract with the given name, or None if not found."""
        ...

    @abstractmethod
    def get_data(
        self, name: str, columns: list[str], *, unique: bool = True
    ) -> pd.DataFrame:
        """Get the data for contract and columns specified.

        Implementations MUST return the stored rows irrespective of the
        caller's read permissions. These values are used for integrity
        checking, where a value exists whether or not the caller is allowed to
        see it: a permission-scoped read hides values the caller cannot read,
        so duplicates are admitted and rows referencing a hidden value are
        wrongly rejected. This obligation cannot be expressed as a parameter,
        because this package has no notion of the access model an
        implementation reads behind.

        Args:
            name (str): The name of the contract.
            columns (list[str]): The list of columns to retrieve.
            unique (bool): Whether to return only unique rows. This is a cost
                hint rather than a correctness requirement — the integrity
                checks build a set of the returned values either way, so
                duplicates are harmless. Passing `True` avoids transferring
                every row of a large referenced table. Defaults to `True`.

        Returns:
            pd.DataFrame: The data for the specified contract and columns.
        """
        ...
