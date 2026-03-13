from abc import ABC
from typing import Self

import pandas as pd

from crosscontract import CrossClient
from crosscontract.contracts.schema.fields.base import BaseField
from crosscontract.contracts.schema.reference import ForeignKeys
from crosscontract.crossclient.services import ContractResource


class CrossBaseVariable(ABC):  # noqa: B024
    """Abstract base for variables obtained from the CROSS data platform.
    This class provides common functionality for fetching data,
    properties, and dunder methods.

    Args:
        contract_resource: The ContractResource object representing the contract on
            the CROSS platform.
    """

    def __init__(
        self,
        contract_resource: ContractResource,
    ):
        self._contract_resource = contract_resource
        self._data: pd.DataFrame | None = None

    @classmethod
    def from_client(
        cls,
        client: CrossClient,
        contract_name: str,
    ) -> Self:
        """Build from a contract fetched via the client.

        Label is derived from the contract title unless explicitly overridden.

        Args:
            client: An instance of CrossClient to fetch contract details.
            contract_name: The name of the contract to fetch.
        """
        cr = client.contracts.get(contract_name)
        return cls(contract_resource=cr)

    @property
    def contract_resource(self) -> ContractResource:
        """ContractResource as obtained from CROSS platform"""
        return self._contract_resource

    @property
    def name(self) -> str:
        """The name of the variable, derived from the contract name."""
        return self.contract_resource.contract.name

    @property
    def description(self) -> str:
        """A human-readable description of the variable"""
        return self.contract_resource.contract.description

    @property
    def title(self) -> str | None:
        """A human-readable title of the variable"""
        return getattr(self.contract_resource.contract, "title", None)

    @property
    def foreign_keys(self) -> ForeignKeys:
        """A dictionary mapping field names to their corresponding foreign key
        references."""
        return self._contract_resource.contract.tableschema.foreignKeys

    @property
    def data(self) -> pd.DataFrame:
        """Lazily load and return the data for this variable."""
        if self._data is None:
            self._data = self._fetch_data()
        return self._data.copy()

    @property
    def fields(self) -> list[BaseField]:
        """Return the list of fields/columns in the data."""
        return self.contract_resource.contract.tableschema.fields

    @property
    def field_names(self) -> list[str]:
        """Return the list of field/column names in the data."""
        return [field.name for field in self.fields]

    def clear_data_cache(self):
        """Clear the cached data, forcing a refetch on next access."""
        self._data = None

    def _fetch_data(self) -> pd.DataFrame:
        """Fetch the data for this variable from the CROSS platform. The data
        is filtered according to the filters specified when the variable was
        created.

        Returns:
            pd.DataFrame: A DataFrame containing the results for the specified contract.
        """
        df = self.contract_resource.get_data()
        return df
