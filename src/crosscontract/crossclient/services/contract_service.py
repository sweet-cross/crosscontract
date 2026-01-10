import io
from typing import TYPE_CHECKING, Any, Literal

import pandas as pd

from crosscontract import CrossContract

from ..exceptions import ResourceNotFoundError, raise_from_response
from .contract_resource import ContractResource

if TYPE_CHECKING:  # pragma: no cover
    from ..crossclient import CrossClient


class ContractService:
    """
    Entry point for operations on the collection of contracts.
    """

    _api_version_prefix = "/api/v1"
    _route = f"{_api_version_prefix}/contract/"

    def __init__(self, client: "CrossClient"):
        """Initialize the ContractService. The ContractService is responsible for
        managing contracts on the CROSS platform. It provides methods to create,
        retrieve, list, and delete contracts.

        Args:
            client (CrossClient): The CrossClient instance to use for API calls.
        """
        self._client = client

    def create(
        self, contract: CrossContract, activate: bool = False
    ) -> ContractResource:
        """Create a new contract on the CROSS platform

        Args:
            contract (CrossContract): The contract data to create.
            activate (bool): Whether to activate the contract upon creation.
                Defaults to False.

        Raises:
            httpx.HTTPStatusError: If the request fails.

        Returns:
            ContractResource: The created contract object.
        """
        # 1. Create the contract on the platform
        json_payload = contract.model_dump(mode="json")
        response = self._client.post(self._route, json=json_payload)
        raise_from_response(response)

        # 2. Extract info from response
        resp = response.json()
        contract = CrossContract.model_validate(resp["contract"])
        status = resp["status"]

        # 3. Activate the contract if requested
        if activate:
            status = self._client.contracts.change_status(contract.name, "Active")

        # 4. Return the ContractResource
        return ContractResource(self, contract=contract, status=status)

    def overview(self) -> pd.DataFrame:
        """Get a DataFrame with an overview of all contracts, their status, and
        metadata.

        Returns:
            pd.DataFrame: DataFrame containing contract overviews.
        """
        endpoint = f"{self._route}metadata"
        response = self._client.get(endpoint)
        raise_from_response(response)
        df = pd.DataFrame(response.json())
        return df

    def get_list(self) -> dict[str, ContractResource]:
        """
        Lists all available contracts as ContractResource objects.

        Returns:
            dict[str, ContractResource]: Dictionary of contract resources keyed
                by contract name.
        """
        endpoint = self._route
        response = self._client.get(endpoint)
        raise_from_response(response)
        json_body = response.json()
        return {
            item["name"]: ContractResource(
                self,
                contract=CrossContract.model_validate(item["contract"]),
                status=item["status"],
            )
            for item in json_body
        }

    def get(self, name: str) -> ContractResource:
        """Get contract from the CROSS platform by name.

        Args:
            name (str): The name of the contract.

        Raises:
            httpx.HTTPStatusError: If the request fails.

        Returns:
            ContractResource: The contract resource object.
        """
        endpoint = f"{self._route}{name}"
        response = self._client.get(endpoint)
        raise_from_response(response)
        json_body = response.json()
        contract = CrossContract.model_validate(json_body["contract"])
        return ContractResource(self, contract=contract, status=json_body.get("status"))

    def delete(self, name: str, hard: bool = False) -> None:
        """Delete a contract by name if it exists. A contract can only be deleted
        if:
        1. Contract is in "Draft" status
        2. Contract status is "Retired" and the data associated with the contract
            is deleted

        If `hard` is set to True, the contract and all associated data will be deleted.
        Note: This is a dangerous operation and should be used with caution. Usually,
            admin rights are required.

        Args:
            name (str): The name of the contract to delete.
            hard (bool): Whether to perform a hard delete (including data).
                Note: This is a dangerous operation and should be used with caution.
                    it will delete all data associated with the contract. Usually,
                    admin rights are required.
        """
        if hard:
            # if in active or suspended status, change to retired first
            # if in draft status, this will raise an error, which is fine
            try:
                self.change_status(name, "Retired")
            except Exception:
                pass
            # delete all associated data
            try:
                self._drop_data_table(name)
            except Exception:
                pass
        # delete the contract
        try:
            res = self._client.delete(f"{self._route}{name}")
            raise_from_response(res)
        except ResourceNotFoundError:
            # be silent if the contract does not exist
            return

    def change_status(
        self,
        name: str,
        status: Literal["Draft", "Active", "Suspended", "Retired"],
    ) -> str:
        """Change the status of a contract. Allowable status transitions are enforced
        by the CROSS platform. The allowable statuses are:
            1. Draft
            2. Active
            3. Suspended
            4. Retired
        Allowed transitions:
            - Draft -> Active
            - Active -> Suspended
            - Suspended -> Active
            - Active -> Retired
            - Suspended -> Retired

        Args:
            name (str): The name of the contract to change status.
            status (Literal["Draft", "Active", "Suspended", "Retired"]):
                The new status for the contract.

        Raises:
            httpx.HTTPStatusError: If the request fails.

        Returns:
            str: The updated status of the contract.
        """
        payload = {"status": status}
        res = self._client.patch(f"{self._route}{name}/state", json=payload)
        raise_from_response(res)
        return res.json()

    def _drop_data_table(self, name: str) -> None:
        """Drop the table storing the data for the given contract. This deletes all
        data associated with the contract. Dropping the data table is irreversible.
        It can only be performed if the contract is in "Retired" status.

        Note: This operation is ireversible and will delete all data associated with the
        contract.

        Args:
            name (str): The name of the contract whose data to delete.
        """
        # delete the contract
        res = self._client.delete(f"{self._route}{name}/storage")
        raise_from_response(res)

    def _add_data(self, name: str, data: pd.DataFrame) -> None:
        """Add data for the contract on the CROSS platform. Note that this method
        does not perform schema validation. Use ContractResource.add_data() to
        validate data against the contract schema before uploading. I.e., it is
        better to use:
            contract = client.contracts.get(name)
            contract.add_data(data)  # <-- performs validation

        Args:
            name (str): The name of the contract to add data to.
            data (pd.DataFrame): The data to be added.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """
        endpoint = f"{self._route}{name}/data"
        # construct the payload
        with io.BytesIO(data.to_csv(index=False).encode("utf-8")) as csv_buffer:
            files = {"file": (f"{name}.csv", csv_buffer, "text/csv")}
            res = self._client.post(endpoint, files=files)
        raise_from_response(res)
        return

    def _get_data(
        self,
        name: str,
        columns: list[str] | None = None,
        filters: dict[str, str] | None = None,
        unique: bool = False,
    ) -> pd.DataFrame:
        """Get data for the contract from the CROSS platform.

        Args:
            name (str): The name of the contract to get data for.
            columns (list[str] | None): Optional list of columns to retrieve.
                If None, all columns are retrieved.
            filters (dict[str, str] | None): Optional dictionary of filters to apply.
                The keys are column names and the values are the filter values.
                Currently, only equality filters are supported and only one value per
                filter.
            unique (bool): Whether to return only unique rows.

        Returns:
            pd.DataFrame: The data associated with the contract.
        """
        endpoint = f"{self._route}{name}/data"
        params: dict[str, Any] = {}
        if columns:
            params["columns"] = ",".join(columns)
        if filters:
            for key, value in filters.items():
                params[key] = value
        if unique:
            params["unique"] = "true"

        # perform the request using parquet as data format for efficiency
        params["format"] = "parquet"
        response = self._client.get(endpoint, params=params)
        raise_from_response(response)
        # read the CSV data into a DataFrame
        df = pd.read_parquet(io.BytesIO(response.content))
        return df
