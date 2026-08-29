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
        self, name: str, columns: list[str], *, unique: bool = False
    ) -> pd.DataFrame:
        """Get the data for contract and columns specified.

        Args:
            name (str): The name of the contract.
            columns (list[str]): The list of columns to retrieve.
            unique (bool): Whether to return only unique rows.
                Defaults to False.


        Returns:
            pd.DataFrame: The data for the specified contract and columns.
        """
        ...
