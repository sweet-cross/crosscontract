from typing import Any

import pandas as pd

from crosscontract import CrossClient
from crosscontract.contracts.contracts.cross_contract import ContractType

from .variables import (
    CrossBaseDimension,
    CrossDataVariable,
    CrossDimension,
    CrossFlexibleDimension,
)


class CrossRegistry:
    """A data registry to interact with the CROSS data platform."""

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        client: CrossClient | None = None,
    ):
        """Initialize the CrossRegistry with either a CrossClient instance or
        username/password.

        Args:
            username (str | None): The username or email to connect to CROSS platform.
            password (str | None): The password to connect to CROSS platform.
            client (CrossClient | None): An optional CrossClient instance. If provided,
                it will be used directly. If not, a new client will be created using
                the provided username and password.
        """
        if client is None:
            if username is None or password is None:
                raise ValueError(
                    "Either a CrossClient instance or both username and password must "
                    "be provided."
                )
            client = CrossClient(username=username, password=password)

        self._client = client
        self._variables: dict[str, CrossDataVariable | CrossBaseDimension] = {}

    def __getattr__(self, name: str) -> CrossDataVariable | CrossBaseDimension:
        """Magic method to allow dot notation access with lazy loading."""
        # 1. Prevent IDEs and Python internals from triggering API calls!
        if name.startswith("_"):
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{name}'"
            )

        # 2. Route through get_variable for auto-loading
        try:
            return self.get_variable(name)
        except KeyError as e:
            # 3. Cast the KeyError back to an AttributeError so Python's
            # internal hasattr() functions still work correctly.
            raise AttributeError(str(e)) from e

    def __getitem__(self, name: str) -> CrossDataVariable | CrossBaseDimension:
        """
        Magic method to allow dictionary-style access.
        Usage: registry["my_variable_name"]
        """
        return self.get_variable(name)

    def __dir__(self) -> list[str]:
        """
        Overrides the built-in dir() function to include your dynamic variables
        in IDE autocomplete menus (like Jupyter tab-completion).
        """
        return list(super().__dir__()) + list(self._variables.keys())

    def get_contract_overview(
        self,
        contract_type: ContractType | list[ContractType] | None = None,
    ) -> pd.DataFrame:
        """Fetch an overview of available contracts from the CROSS platform.

        Args:
            contract_type: Optional filter restricting the result to one or
                more contract types (e.g. ``"Dimension"`` or
                ``["Dimension", "FlexibleDimension"]``). If ``None``, all
                contracts are returned.

        Returns:
            pd.DataFrame: DataFrame with ``name``, ``title``, ``description``,
                and ``contract_type`` columns.
        """
        df = self._client.contracts.overview()
        if contract_type is not None:
            wanted = (
                [contract_type]
                if isinstance(contract_type, str)
                else list(contract_type)
            )
            df = df[df["contract_type"].isin(wanted)]
        return df[["name", "title", "description", "contract_type"]]

    @property
    def contract_overview(self) -> pd.DataFrame:
        """Overview of all contracts on the CROSS platform as a pandas DataFrame."""
        return self.get_contract_overview()

    def add_variable(
        self,
        name: str,
        filters: dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> CrossDataVariable | CrossBaseDimension:
        """Add a variable to the registry by fetching it from the CROSS platform.

        Args:
            name (str): The name of the data contract. It is also used as name
                attribute name under which the variable will be accessible in the
                registry.
            filters (dict[str, Any] | None): Additional filters to apply when
                fetching data (optional).
            overwrite (bool): Whether to overwrite an existing variable with the
                same name.
                Defaults to False.

        Returns:
            CrossDataVariable | CrossBaseDimension: The loaded variable instance.
        """
        if name in self._variables:
            if isinstance(self._variables[name], CrossBaseDimension):
                raise ValueError(
                    f"Variable '{name}' is a Dimension and cannot be overwritten."
                )
            if not overwrite:
                raise ValueError(
                    f"Variable '{name}' already exists in the registry. "
                    "Set overwrite=True to replace it."
                )

        cr = self._client.contracts.get(name)

        if cr.is_dimension:
            # Star schema: dimensions only self-reference, so there are no
            # external FKs to resolve here.
            wrapper_cls: type[CrossBaseDimension] = (
                CrossDimension
                if cr.contract.contract_type == "Dimension"
                else CrossFlexibleDimension
            )
            self._variables[name] = wrapper_cls(cr)
            return self._variables[name]

        # General / ValueVariable -> data variable; resolve FK targets directly.
        # Under the star schema, FK targets are always dimensions (which do not
        # have outgoing FKs), so a single-level walk is sufficient.
        var = CrossDataVariable(cr, filters=filters)
        self._variables[name] = var

        for fk in var.foreign_keys or []:
            ref_name = fk.reference.resource
            if ref_name is None:
                continue  # self-reference
            if ref_name not in self._variables:
                self.add_variable(ref_name)
            target = self._variables[ref_name]
            # Composite-FK dimensions are loaded but not auto-attached:
            # add_dimension keys by single column name. Users can still reach
            # them via registry[ref_name].
            if isinstance(target, CrossBaseDimension) and len(fk.fields) == 1:
                var.add_dimension(target)
        return var

    def get_variable(self, name: str) -> CrossDataVariable | CrossBaseDimension:
        """Explicit getter method for retrieving a variable (with lazy loading)."""
        if name not in self._variables:
            try:
                # Auto-load the variable
                self.add_variable(name)
            except Exception as e:
                # Chain the exception using 'from e' so the user can see
                # IF it was a network/auth error from the client!
                raise KeyError(
                    f"Could not load variable '{name}' into registry. "
                    f"Original error: {str(e)}"
                ) from e

        return self._variables[name]
