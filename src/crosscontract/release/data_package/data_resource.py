"""A `CrossDataResource` is the frictionless compliant representation of a
`CrossContract` together with the description of the data source. The data source is
always a file that is assumed to be distributed within a (zip) folder together with
this descriptor. I.e., the `CrossDataResource` is a self-contained. It the
same as the `CrossContract` but augments by a description of the data file.

"""

from typing import Literal, Self

from pydantic import Field, computed_field, model_validator

from ...contracts.contracts.cross_contract import CrossContract

Formats = Literal["csv", "parquet"]
Encodings = Literal["utf-8", "utf-16", "latin-1"]


class CrossDataResource(CrossContract):
    """
    A `CrossDataResource` is the frictionless compliant representation of a
    `CrossContract` together with the description of the data source. The data
    source is always a file that is assumed to be distributed within a (zip) folder
    together with this descriptor. I.e., the `CrossDataResource` is a self-contained.
    It the same as the `CrossContract` but augments by a description of the data file.

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

    @computed_field(
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
            contract (CrossContract): The base contract to convert.
            path (str): The path to the data file.
            format (Formats, optional): The format of the data file. Defaults to "csv".
            encoding (Encodings, optional): The encoding of the data file.
                Defaults to "utf-8".

        Returns:
            Self: A new instance of `CrossDataResource` with the
                provided metadata.
        """
        return cls(
            **contract.model_dump(),
            path=path,
            format=format,
            encoding=encoding,
        )
