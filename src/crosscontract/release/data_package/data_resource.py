"""A `CrossDataResource` is the frictionless compliant representation of a
`CrossContract` together with the description of the data source. The data source is
always a file that is assumed to be distributed within a (zip) folder together with
this descriptor. I.e., the `CrossDataResource` is self-contained. It is the same as
the `CrossContract` but augmented by a description of the data file.

"""

from typing import Any, Literal, Self

from pydantic import Field, computed_field, model_validator

from ...contracts.contracts.cross_contract import CrossContract

Formats = Literal["csv", "parquet"]
Encodings = Literal["utf-8", "utf-16", "latin-1"]


class CrossDataResource(CrossContract):
    """
    A `CrossDataResource` is the frictionless compliant representation of a
    `CrossContract` together with the description of the data source. The data
    source is always a file that is assumed to be distributed within a (zip) folder
    together with this descriptor. I.e., the `CrossDataResource` is self-contained.
    It is the same as the `CrossContract` but augmented by a description of the
    data file.

    Attributes:
        path (str): The path to the data file. This is a required field.
        format (Formats): The format of the data file. Either 'csv' or 'parquet'.
            Defaults to 'csv'.
        encoding (Encodings): The encoding of the data file. Either 'utf-8',
            'utf-16', or 'latin-1'. Defaults to 'utf-8'.
        profile (Literal['tabular-data-resource', 'data-resource']): The profile of
            the data resource. 'tabular-data-resource' for CSV files and
            'data-resource' for Parquet files. This is automatically assigned based
            on the format.
    """

    path: str = Field(
        description=("The path to the data file. This is a required field."),
    )
    format: Formats = Field(
        default="csv",
        description=(
            "The format of the data file. Either 'csv' or 'parquet'. Defaults to 'csv'."
        ),
    )
    encoding: Encodings = Field(
        default="utf-8",
        description=(
            "The encoding of the data file. Either 'utf-8', 'utf-16', or 'latin-1'."
            " Defaults to 'utf-8'."
        ),
    )

    @computed_field(  # type: ignore[prop-decorator]
        description=(
            "The profile of the data resource. Assigned automatically based on format."
        )
    )
    @property
    def profile(self) -> Literal["tabular-data-resource", "data-resource"]:
        """Compute the correct profile according to the data format.
        csv -> tabular-data-resource
        parquet -> data-resource

        Returns:
            Literal['tabular-data-resource', 'data-resource']: The profile of the
                data resource.
        """
        if self.format == "csv":
            return "tabular-data-resource"
        return "data-resource"

    @model_validator(mode="after")
    def _check_file_name_consistency(self) -> Self:
        """Validate that the file extension in the path is consistent with the declared
        format.

        Raises:
            ValueError: If the file extension does not match the declared format.

        Returns:
            Self: The validated instance of `CrossDataResource`.
        """
        if self.format == "csv" and not self.path.endswith(".csv"):
            raise ValueError(
                f"File path '{self.path}' does not have a .csv extension "
                f"consistent with declared format 'csv'."
            )
        if self.format == "parquet" and not self.path.endswith(".parquet"):
            raise ValueError(
                f"File path '{self.path}' does not have a .parquet extension "
                f"consistent with declared format 'parquet'."
            )
        return self

    @classmethod
    def from_contract(
        cls,
        contract: CrossContract,
        path: str,
        format: Formats = "csv",
        encoding: Encodings = "utf-8",
    ) -> Self:
        """
        Create a `CrossDataResource` from a `CrossContract` by adding data resource
        metadata.

        Args:
            contract (CrossContract): The base contract to convert. Must be a plain
                `CrossContract`, not an already-bound `CrossDataResource`.
            path (str): The path to the data file.
            format (Formats, optional): The format of the data file. Defaults to "csv".
            encoding (Encodings, optional): The encoding of the data file.
                Defaults to "utf-8".

        Returns:
            Self: A new instance of `CrossDataResource` with the
                provided metadata.

        Raises:
            TypeError: If `contract` is a `CrossDataResource`, which already carries
                its own data specification and would collide with the `path`,
                `format`, and `encoding` arguments.
        """
        if isinstance(contract, CrossDataResource):
            raise TypeError(
                "from_contract expects a plain CrossContract, not a CrossDataResource. "
                "The resource already carries its own data specification."
            )
        return cls(
            **contract.model_dump(),
            path=path,
            format=format,
            encoding=encoding,
        )

    def to_descriptor(self) -> dict[str, Any]:
        """Render the Frictionless data-resource descriptor.

        Serializes the resource and remaps the internal `tableschema` key to the
        Frictionless-standard `schema`. This is the single point where the release
        wire-format is applied; the model itself stays neutral and round-trippable
        via the ordinary `tableschema` field, so `model_dump()` and
        `model_validate()` remain symmetric.

        Returns:
            dict[str, Any]: The Frictionless-compatible resource descriptor, ready
                to be written alongside the data file in the (zip) archive.
        """
        descriptor = self.model_dump(mode="json")
        descriptor["schema"] = descriptor.pop("tableschema")
        return descriptor

    def to_server(self) -> dict[str, Any]:
        """Reject server serialization — a resource is not a server contract.

        A `CrossDataResource` is an egress/release artifact that binds a contract to
        a physical file; it is never submitted to the platform as a contract. The
        inherited `CrossContract.to_server` would otherwise emit the resource-only
        fields (`path`, `format`, `encoding`, `profile`) and produce an invalid
        payload, so it is disabled here.

        Raises:
            NotImplementedError: Always. Operate on the underlying `CrossContract`
                to talk to the platform.
        """
        raise NotImplementedError(
            "CrossDataResource is a release artifact, not a server contract. "
            "Operate on the underlying CrossContract to talk to the platform."
        )

    @classmethod
    def from_server(cls, data: dict[str, Any]) -> "CrossDataResource":
        """Reject server construction — a resource is not built from a server payload.

        Server payloads describe `CrossContract`s and carry no data specification
        (`path`, `format`, `encoding`), so they cannot construct a self-contained
        resource. Build the `CrossContract` from the server first, then bind a file
        with `from_contract`.

        Raises:
            NotImplementedError: Always. Use `CrossContract.from_server` followed by
                `CrossDataResource.from_contract`.
        """
        raise NotImplementedError(
            "CrossDataResource cannot be built from a server payload, which carries "
            "no data specification. Use CrossContract.from_server, then "
            "CrossDataResource.from_contract."
        )
