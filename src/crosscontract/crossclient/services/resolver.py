from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from crosscontract.contracts import ContractResolver, CrossContract
from crosscontract.crossclient.exceptions import ResourceNotFoundError

if TYPE_CHECKING:
    from crosscontract.crossclient import ContractService


class ClientContractResolver(ContractResolver):
    """Reads contracts and their data from the CROSS platform.

    Answers the two questions a contract cannot answer on its own: what another
    contract looks like, and which values are already stored under it. Used when
    validating data against a contract that references other contracts.

    Attributes:
        service (ContractService): The service used to reach the platform.
    """

    def __init__(self, service: ContractService):
        """Initialise the resolver with the service it reads through.

        Args:
            service (ContractService): The service used to reach the platform.
        """
        self._service = service

    def resolve(self, name: str) -> CrossContract | None:
        """Get a contract by name.

        Args:
            name (str): The name of the contract.

        Returns:
            CrossContract | None: The contract, or `None` if the platform has no
            contract with that name.
        """
        try:
            return self._service.get(name).contract
        except ResourceNotFoundError:
            return None

    def get_data(
        self, name: str, columns: list[str], *, unique: bool = True
    ) -> pd.DataFrame:
        """Get the stored values of the given columns for a contract.

        The read is not narrowed to the caller's own project, and must not be:
        the values are used to check that keys are unique and that references
        point at something that exists. A key occupies its name whoever owns it,
        so hiding the rows of other projects would let duplicates through and
        reject rows that reference a value the caller cannot see.

        Args:
            name (str): The name of the contract to read from.
            columns (list[str]): The columns to retrieve.
            unique (bool): Whether to return only unique rows. Defaults to
                `True`, which keeps the response small; the result is the same
                either way.

        Returns:
            pd.DataFrame: The requested columns of the named contract.
        """
        return self._service._get_data(name, columns=columns, unique=unique)
