from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from crosscontract.contracts import ContractResolver, CrossContract
from crosscontract.crossclient.exceptions import ResourceNotFoundError

if TYPE_CHECKING:
    from crosscontract.crossclient import ContractService


class ClientContractResolver(ContractResolver):
    def __init__(self, service: ContractService):
        self._service = service

    def resolve(self, name: str) -> CrossContract | None:
        try:
            return self._service.get(name).contract
        except ResourceNotFoundError:
            return None

    def get_data(self, name, columns, *, unique=True) -> pd.DataFrame:
        return self._service._get_data(name, columns=columns, unique=unique)
