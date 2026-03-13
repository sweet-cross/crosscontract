import warnings
from typing import Any

from crosscontract import CrossClient

from .base_variable import CrossBaseVariable
from .data_variable import CrossDataVariable
from .dimension import CrossDimension


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
        self._variables: dict[str, CrossBaseVariable] = {}
        self._loading: set[str] = set()

    def __getattr__(self, name: str) -> CrossDataVariable | CrossDimension:
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

    def __getitem__(self, name: str) -> CrossDataVariable | CrossDimension:
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

    def add_variable(
        self,
        name: str,
        filters: dict[str, Any] | None = None,
        overwrite: bool = False,
    ):
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
        """
        if name in self._variables:
            if isinstance(self._variables[name], CrossDimension):
                raise ValueError(
                    f"Variable '{name}' is a Dimension and cannot be overwritten."
                )
            if not overwrite:
                raise ValueError(
                    f"Variable '{name}' already exists in the registry. "
                    "Set overwrite=True to replace it."
                )

        # todo: make dimensions identifiable by contract
        if name.startswith("dim_"):
            self._variables[name] = CrossDimension.from_client(self._client, name)
            # return as we do not allow dimensions to reference other dimensions
            # TODO: enforce that with dimension contract
            return
        else:
            self._variables[name] = CrossDataVariable.from_client(
                self._client, name, filters=filters
            )

        # resolve the foreign key references, fetch the respective contracts, and
        # hydrate them into the variable
        # NOTE: circular foreign key references are assumed to be prevented
        # upstream by the CROSS platform upon contract injection.
        # The guard below is a defensive measure only.
        self._loading.add(name)
        try:
            fks = self._variables[name].foreign_keys or []
            for fk in fks:
                ref_name = fk.reference.resource
                if ref_name is None:
                    continue  # skip self-reference
                if ref_name not in self._variables:
                    if ref_name in self._loading:
                        warnings.warn(
                            f"Circular foreign key reference detected: "
                            f"'{ref_name}' is already being loaded while "
                            f"resolving '{name}'. Skipping.",
                            stacklevel=2,
                        )
                        continue  # skip circular reference
                    self.add_variable(ref_name)
                # if it is a dimension, add it to the variable,
                # otherwise skip (we only support dimensions as FK targets for now)
                if isinstance(self._variables[ref_name], CrossDimension):
                    self._variables[name].add_dimension(self._variables[ref_name])
        finally:
            self._loading.remove(name)

    def get_variable(self, name: str) -> CrossDataVariable | CrossDimension:
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
