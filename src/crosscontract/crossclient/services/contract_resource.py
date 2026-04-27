from typing import TYPE_CHECKING, Any, Literal

import pandas as pd
from pydantic import BaseModel

from crosscontract import CrossContract
from crosscontract.contracts.schema import SchemaValidationError
from crosscontract.contracts.schema.subschemas import BaseDimensionSchema

from ..exceptions import ValidationError

if TYPE_CHECKING:  # pragma: no cover
    from .contract_service import ContractService


ContractStatus = Literal["Draft", "Active", "Suspended", "Retired"]


class _ContractEntryPayload(BaseModel):
    """Client-side mirror of the server's ``DataContractEntryResponse``.

    Centralising the shape here gives us validation at the API boundary and a
    single place to adjust if the server response evolves.
    """

    name: str
    status: ContractStatus
    contract_type: str
    contract: dict[str, Any]


class ContractResource:
    """A handle to a contract that exists on the CROSS platform.

    ContractResources are read-only wrappers around contract data fetched from
    the CROSS platform. They are produced exclusively by ``ContractService``
    methods (``create``, ``get``, ``get_list``); end users do not construct them
    directly.

    Attributes:
        name (str): The name of the contract.
        status (str): The status of the contract.
        contract (CrossContract): The full contract details.
        contract_type (str): The type of the contract, e.g. ``"General"``.
        service (ContractService): The owning ``ContractService``.
    """

    def __init__(
        self,
        service: "ContractService",
        payload: _ContractEntryPayload,
    ):
        """Initialise from a parsed server payload.

        Most callers should use :meth:`from_response` to parse a raw JSON dict;
        this constructor takes a pre-validated payload to keep tests direct.
        """
        self._service = service
        self._name = payload.name
        self._status = payload.status
        self._contract_type = payload.contract_type
        self._contract = CrossContract.from_server(payload.contract)

    @classmethod
    def from_response(
        cls,
        service: "ContractService",
        response_json: dict[str, Any],
    ) -> "ContractResource":
        """Build a ContractResource from a raw server response dict."""
        payload = _ContractEntryPayload.model_validate(response_json)
        return cls(service, payload)

    @property
    def name(self) -> str:
        return self._name

    @property
    def status(self) -> ContractStatus:
        return self._status

    @property
    def contract_type(self) -> str:
        return self._contract_type

    @property
    def contract(self) -> CrossContract:
        return self._contract

    @property
    def is_dimension(self) -> bool:
        """True if the contract's tableschema is a dimension schema."""
        return isinstance(self._contract.tableschema, BaseDimensionSchema)

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

    def change_status(self, status: ContractStatus) -> None:
        """Change the status of the contract.

        Args:
            status (ContractStatus): The new status for the contract.
        """
        self._service.change_status(self.name, status)
        self._status = status

    def refresh(self) -> None:
        """Re-fetch the contract details from the CROSS platform."""
        remote = self._service.get(self.name)
        if remote.name != self.name:
            raise ValueError(
                f"Fetched contract name '{remote.name}' does not match "
                f"resource name '{self.name}'."
            )
        self._contract = remote.contract
        self._status = remote.status
        self._contract_type = remote.contract_type

    def _prepare_dataframe_csv_upload(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare a DataFrame for CSV upload by formatting datetime columns.

        This method converts datetime-typed fields defined in the contract's
        table schema from pandas datetime dtypes to string values using the
        field's configured format. Columns of other data types are left
        unchanged.

        Args:
            df (pd.DataFrame): The input DataFrame to be prepared for CSV upload.

        Returns:
            pd.DataFrame: The prepared DataFrame ready for CSV upload.
        """
        # convert datetime fields to string with correct format
        dt_fields = [
            f
            for f in self.contract.tableschema.field_iterator()
            if f.type == "datetime" and f.name in df.columns
        ]
        if len(dt_fields) == 0:
            return df
        df_out = df.copy(deep=False)
        for field in dt_fields:
            if pd.api.types.is_datetime64_any_dtype(df[field.name]):
                df_out[field.name] = df_out[field.name].dt.strftime(field.format)
        return df_out

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
        data_out = self._prepare_dataframe_csv_upload(data)
        self._service._add_data(self.name, data_out)

    def get_data(
        self,
        columns: list[str] | None = None,
        filters: dict[str, str] | None = None,
        unique: bool = False,
    ) -> pd.DataFrame:
        """Get data for the contract from the CROSS platform.

        Args:
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
        """Validate a DataFrame against the schema of the contract.
        It allows to provide existing primary
        key and foreign key values for validation. If provided, the primary key
        uniqueness is checked against the union of the existing and the DataFrame
        values. Similarly, foreign key integrity is checked against the union of
        existing and DataFrame values in case of self-referencing foreign keys.

        The validation is performed including primary key and foreign key checks
        that may require fetching existing key values from the CROSS platform.

        Args:
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
