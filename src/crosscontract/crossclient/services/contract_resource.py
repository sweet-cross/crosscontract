from typing import TYPE_CHECKING, Any, Literal

import pandas as pd
from pydantic import BaseModel

from crosscontract import CrossContract
from crosscontract.contracts.schema import SchemaValidationError
from crosscontract.contracts.schema.subschemas import BaseDimensionSchema

from ..exceptions import ValidationError
from .resolver import ClientContractResolver

if TYPE_CHECKING:  # pragma: no cover
    from .contract_service import ContractService, FilterValue


ContractStatus = Literal["Draft", "Active", "Suspended", "Retired"]


class _ContractEntryPayload(BaseModel):
    """Client-side mirror of the server's `DataContractEntryResponse`.

    Centralizing the shape here gives us validation at the API boundary and a
    single place to adjust if the server response evolves.
    """

    name: str
    status: ContractStatus
    contract_type: str
    contract: dict[str, Any]


class ContractResource:
    """A handle to a contract that exists on the CROSS platform.

    ContractResources are read-only wrappers around contract data fetched from
    the CROSS platform. They are produced exclusively by `ContractService`
    methods (`create`, `get`, `get_list`); end users do not construct them
    directly.

    Attributes:
        name (str): The name of the contract.
        status (str): The status of the contract.
        contract (CrossContract): The full contract details.
        contract_type (str): The type of the contract, e.g. `"General"`.
        service (ContractService): The owning `ContractService`.
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

    def add_data(
        self,
        data: pd.DataFrame,
        validate: bool = True,
        *,
        project_name: str | None = None,
    ) -> None:
        """Add data for the contract on the CROSS platform.

        The rows are stored as owned by the resolved project.

        Args:
            data (pd.DataFrame): The data to be added.
            validate (bool): Whether to validate the data against the contract
                schema before uploading. Defaults to True.
            project_name (str | None): Optional project name under which the data
                are submitted. If None, the CROSS platform infers the project from the
                caller's memberships, which succeeds only when there is exactly one.

        Raises:
            ValidationError: If the data does not conform to the contract schema.
            CrossClientError: If the upload fails. Raised via
                `raise_from_response` as a more specific client exception such
                as `ResourceNotFoundError` or `ConflictError`.
        """
        if validate:
            # validate data against contract schema at the client side
            self.validate_dataframe(data)
        data_out = self._prepare_dataframe_csv_upload(data)
        self._service._add_data(self.name, data_out, project_name=project_name)

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
        check_existing_primary_key: bool = False,
        check_existing_foreign_key: bool = False,
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
            check_existing_primary_key (bool): If True, check existing primary
                key values. Default is False.
            check_existing_foreign_key (bool): If True, check existing foreign key
                values. Default is False.
            lazy (bool): If True, collect all validation errors and raise them together.
                If False, raise the first validation error encountered.
                Default is True.

        Raises:
            ValidationError: If the DataFrame does not conform to the schema.
        """
        resolver = ClientContractResolver(self._service)
        try:
            self.contract.validate_data(
                df,
                resolver=resolver,
                check_existing_primary_key=check_existing_primary_key,
                check_existing_foreign_key=check_existing_foreign_key,
                lazy=lazy,
            )
        except SchemaValidationError as e:
            # convert to CrossClient ValidationError
            raise ValidationError(
                message=f"DataFrame validation against contract '{self.name}' "
                "schema failed.",
                validation_errors=e.to_list(),
            ) from e

    def drop_data(self) -> None:
        """Drop the storage table backing the contract on the CROSS platform.

        This is a decommissioning operation: it discards the data of **every**
        project that submitted under this contract, not only the caller's, and
        requires the contract to be `Retired`. It is restricted to
        administrators. To remove only the rows owned by one project, use
        `delete_data()` — with `confirm_delete_all=True` to clear that
        project's rows entirely.

        Raises:
            CrossClientError: If the request fails. Raised via
                `raise_from_response` as a more specific client exception such
                as `ResourceNotFoundError` or `ConflictError`.
        """
        self._service._drop_data_table(self.name)

    def delete_data(
        self,
        filters: "dict[str, FilterValue | list[FilterValue]]",
        *,
        project_name: str | None = None,
        confirm_delete_all: bool = False,
    ) -> None:
        """Delete rows from the contract's data matching the given equality filters.

        Only rows owned by the resolved project are removed, and the contract
        must be `Active`. `drop_data()` is the wider, separate operation: it
        drops the whole storage table across every project and requires the
        contract to be `Retired`.

        Args:
            filters (dict): Mapping of column name to value (or list of values)
                to match. Values may be str/int/float/bool. Must be non-empty
                unless `confirm_delete_all` is set.
            project_name (str | None): Optional project name for which project the
                data are deleted. If None, the CROSS platform infers the project
                from the caller's memberships, which succeeds only when there is
                exactly one.
            confirm_delete_all (bool): Confirms that an unfiltered delete is
                intended, removing every row the resolved project owns under
                this contract. Required when `filters` is empty, so that a
                filter mapping which collapsed to empty cannot wipe the
                project's rows by accident. Ignored when `filters` is
                non-empty — a filtered delete stays filtered, and the
                confirmation never reaches the CROSS platform. Defaults to
                `False`.

        Raises:
            ValueError: If the contract's cached status is not `"Active"`, or
                if `filters` is empty and `confirm_delete_all` is False. The
                status check is local and uses the cached status; call
                `refresh()` first if the status may have changed on the CROSS
                platform.
            CrossClientError: Propagated from the underlying service/HTTP
                request if the deletion request fails due to client, server,
                or network-related errors.
        """
        if self._status != "Active":
            raise ValueError(
                f"Cannot delete data from contract '{self.name}': status is "
                f"'{self._status}', must be 'Active'. Call refresh() if the "
                "status may have changed on the server."
            )
        self._service._delete_data(
            self.name,
            filters,
            project_name=project_name,
            confirm_delete_all=confirm_delete_all,
        )
