from typing import TYPE_CHECKING, Literal

import pandas as pd

from crosscontract import CrossContract
from crosscontract.contracts.schema import SchemaValidationError

from ..exceptions import ValidationError

if TYPE_CHECKING:  # pragma: no cover
    from .contract_service import ContractService


class ContractResource:
    """A contract that is related to contract on the CROSS platform.

    ContractResources are read-only wrappers around the actual contract data that
    is stored on the CROSS platform. They provide lazy loading of the contract
    details and methods to interact with the contract, such as adding data.

    Attributes:
        name (str): The name of the contract.
        status (str): The status of the contract.
        contract (CrossContract): The full contract details.
        service (ContractService): The ContractService instance used for API calls.
    """

    def __init__(
        self,
        service: "ContractService",
        status: str,
        name: str | None = None,
        contract: CrossContract | None = None,
    ):
        """Initialize the ContractResource.

        Args:
            service (ContractService): The ContractService instance to use for
                API calls.
            name (str | None): The name of the contract.
                Required if contract is not provided.
            contract (CrossContract | None): The CrossContract instance.
                If not provided, the contract details will be fetched lazily
                when accessed.
        """
        self._service = service

        # ensure consistence of the name and contract
        if contract and name and contract.name != name:
            raise ValueError(
                f"Name '{name}' does not match contract name '{contract.name}'."
            )
        elif not name and not contract:
            raise ValueError("Either name or contract must be provided.")
        self._name = name or contract.name  # type: ignore
        self._contract = contract
        self._status = status

    @property
    def name(self) -> str:
        return self._name

    @property
    def status(self) -> str | None:
        return self._status

    @property
    def contract(self) -> CrossContract:
        """The full contract details as a CrossContract object.

        This property uses lazy loading to fetch the contract details from the
        CROSS platform only when accessed for the first time.

        Returns:
            CrossContract: The full contract details.
        """
        if self._contract is None:
            self.refresh()
        return self._contract  # type: ignore

    def __setattr__(self, name, value):
        # 1. Access the class to find the attribute definition
        # We use type(self) to avoid triggering infinite recursion or property getters
        attr = getattr(type(self), name, None)

        # 2. Check if the attribute is a property and if it has no setter
        if isinstance(attr, property) and attr.fset is None:
            raise AttributeError(
                "ContractResource is read-only. Use the methods to update properties."
            )

        # 3. If it's not a read-only property, allow the default behavior
        # This allows setting private variables like self._x = 10
        super().__setattr__(name, value)

    def __repr__(self):
        return f"ContractResource(name={self.name}, status={self.status})"

    def change_status(
        self,
        status: Literal["Draft", "Active", "Suspended", "Retired"],
    ) -> None:
        """Change the status of the contract.

        Args:
            status (Literal["Draft", "Active", "Suspended", "Retired"]):
                The new status for the contract.
        """
        self._service.change_status(self.name, status)
        self._status = status

    def refresh(self):
        """Fetch the full contract details from the CROSS platform."""
        contract = self._service.get(self.name)
        if contract.name != self.name:
            raise ValueError(
                f"Fetched contract name '{contract.name}' does not match "
                f"resource name '{self.name}'."
            )
        self._contract = contract

    def add_data(self, data: pd.DataFrame, validate: bool = True) -> None:
        """Add data for the contract on in the CROSS platform.

        Args:
            data (pd.DataFrame): The data to be added.
            validate (bool): Whether to validate the data against the contract
                schema before uploading.
                Defaults to True.

        Raises:
            validationError: If the data does not conform to the contract schema.
        """
        if validate:
            # validate data against contract schema at the client side
            self.validate_dataframe(data)
        self._service._add_data(self.name, data)

    def get_data(
        self,
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
        return self._service._get_data(
            name=self.name, columns=columns, filters=filters, unique=unique
        )

    def validate_dataframe(
        self,
        df: pd.DataFrame,
        skip_primary_key_validation: bool = True,
        skip_foreign_key_validation: bool = True,
        lazy: bool = True,
    ):
        """Validate a DataFrame against a schema. It allows to provide existing primary
        key and foreign key values for validation. If provided, the primary key
        uniqueness is checked against the union of the existing and the DataFrame
        values. Similarly, foreign key integrity is checked against the union of
        existing and DataFrame values in case of self-referencing foreign keys.

        The validation is performed including primary key and foreign key checks
        that may require fetching existing key values from the CROSS platform.

        Args:
            schema (Schema): The schema to validate against.
            df (pd.DataFrame): The DataFrame to validate.
            skip_primary_key_validation (bool): If True, skip primary key validation.
                Default is False.
            skip_foreign_key_validation (bool): If True, skip foreign key validation.
                Default is False.
            lazy (bool): If True, collect all validation errors and raise them together.
                If False, raise the first validation error encountered.
                Default is True.

        Raises:
            ValidationError: If the DataFrame does not conform to the schema.
        """
        schema = self.contract.tableschema

        # get the existing primary key values from the platform if needed
        if skip_primary_key_validation:
            primary_key_values = None
        else:
            # fetch the existing primary key values from the platform
            primary_key_values = self.get_primary_key_values()

        # get the existing foreign key values from the platform if needed
        if skip_foreign_key_validation:
            foreign_key_values = None
        else:
            foreign_key_values = self.get_foreign_key_values()

        # validate the dataframe against the schema
        try:
            schema.validate_dataframe(
                df=df,
                primary_key_values=primary_key_values,
                foreign_key_values=foreign_key_values,
                skip_primary_key_validation=skip_primary_key_validation,
                skip_foreign_key_validation=skip_foreign_key_validation,
                lazy=lazy,
            )
        except SchemaValidationError as e:
            # convert to CrossClient ValidationError
            raise ValidationError(
                message=f"DataFrame validation against contract '{self.name}' "
                "schema failed.",
                validation_errors=e.to_list(),
            ) from e

    def get_primary_key_values(self) -> list[tuple] | None:
        """Get the existing primary key values for the contract from the CROSS platform.
        This is needed if you want to perform primary key validation including existing
        values, i.e., to ensure uniqueness of the primary key across both existing
        and new data.

        Returns:
            list[tuple]: A list of tuples representing the existing primary key values.

        Returns:
            list[tuple] | None: A list of tuples representing the existing primary key
                values. Returns None if the contract does not have a primary key defined
                or if there are no existing primary key values.
        """
        schema = self.contract.tableschema

        # if there is no primary key defined, return None
        if not schema.primaryKey:
            return None

        # get the existing primary key values from the platform
        df_primary_key_values = self.get_data(
            columns=schema.primaryKey.root,
            unique=True,
        )

        # if there are no existing primary key values, return None else return the
        # values as list of tuples
        if df_primary_key_values.empty:
            primary_key_values = None
        else:
            primary_key_values = [
                tuple(row)
                for row in df_primary_key_values.itertuples(index=False, name=None)
            ]
        return primary_key_values

    def get_foreign_key_values(self) -> dict[tuple, list[tuple]] | None:
        """Get the existing foreign key values for the contract from the CROSS platform.
        This is needed if you want to perform foreign key validation including existing
        values, i.e., to ensure referential integrity of the foreign keys across both
        existing and new data.

        Returns:
            dict[tuple, list[tuple]] | None: A dictionary where the keys are tuples
                representing the foreign key fields, and the values are lists of tuples
                representing the existing foreign key values. Returns None if the
                contract does not have foreign keys defined or if there are no existing
                foreign key values.
        """
        schema = self.contract.tableschema

        # if there are no foreign keys defined, return None
        if not schema.foreignKeys:
            return None

        foreign_key_values: dict[tuple, list[tuple]] = {}

        # for each foreign key, get the existing foreign key values from the platform
        for fk in schema.foreignKeys.root:
            fk_contract_name = fk.reference.resource or self.name
            fk_field_names = fk.reference.fields

            df_fk = self._service._get_data(
                name=fk_contract_name,
                columns=fk_field_names,
                unique=True,
            )

            foreign_key_values[tuple(fk.fields)] = [
                tuple(row) for row in df_fk.itertuples(index=False, name=None)
            ]

        return foreign_key_values

    def drop_data(self) -> None:
        """Delete all data associated with the contract on the CROSS platform."""
        self._service._drop_data_table(self.name)
