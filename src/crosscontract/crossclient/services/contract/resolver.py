from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from crosscontract.contracts import ContractResolver, CrossContract
from crosscontract.crossclient.exceptions import ResourceNotFoundError

if TYPE_CHECKING:  # pragma: no cover
    from crosscontract.crossclient import ContractService


class CrossContractResolver(ContractResolver):
    """Reads contracts and their data from the CROSS platform.

    Answers the two questions a contract cannot answer on its own: what another
    contract looks like, and which values are already stored under it. Used when
    validating data against a contract that references other contracts.

    Reaches the platform over HTTP through a `ContractService`, so it sees
    whatever the authenticated caller is allowed to read.
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

        Raises:
            CrossClientError: If the read fails for any reason other than the
                contract being absent. Only a missing contract becomes `None`; a
                permission error or a server failure propagates as the more
                specific client exception.
        """
        try:
            return self._service.get(name).contract
        except ResourceNotFoundError:
            return None

    def get_data(
        self, name: str, columns: list[str], *, unique: bool = True
    ) -> pd.DataFrame:
        """Get the stored values of the given columns for a contract.

        Args:
            name (str): The name of the contract to read from.
            columns (list[str]): The columns to retrieve.
            unique (bool): Whether to return only unique rows. Defaults to
                `True`, which keeps the response small; the result is the same
                either way.

        Returns:
            pd.DataFrame: The requested columns of the named contract.

        Raises:
            CrossClientError: If the read fails. Raised via
                `raise_from_response` as a more specific client exception such
                as `ResourceNotFoundError`.
        """
        return self._service._get_data(name, columns=columns, unique=unique)
