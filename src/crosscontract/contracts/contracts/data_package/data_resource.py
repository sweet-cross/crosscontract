"""A `CrossDataResource` is the frictionless compliant respresentation of a `CrossContract`
together with the description of the data source. The data source is
always assumed to be inline, i.e., the `CrossDataResource` is a self-contained. It the
same as the `CrossContract` but augments by a description of the data file

"""

from typing import Literal, Self

from pydantic import Field

from ..cross_contract import CrossContract

Formats = Literal["csv", "parquet"]
Encodings = Literal["utf-8", "utf-16", "latin-1"]


class CrossDataResource(CrossContract):
    """
    A `CrossDataResource` is the frictionless compliant respresentation of a
    `CrossContract` together with the description of the data source. The data
    source is always assumed to be inline, i.e., the `CrossDataResource` is a
    self-contained. It the same as the `CrossContract` but augments by a description
    of the data file.
    """

    format: Formats = Field(default="csv")
    encoding: Encodings = Field(default="utf-8")
    profile: Literal["tabular-data-resource"] = Field(default="tabular-data-resource")

    @classmethod
    def from_contract(
        cls,
        contract: CrossContract,
        format: Formats = "csv",
        encoding: Encodings = "utf-8",
    ) -> Self:
        """
        Create a `CrossDataResource` from a `CrossContract` by adding data resource
        metadata.

        Args:
            contract (CrossContract): The base contract to convert.
            format (Formats, optional): The format of the data file. Defaults to "csv".
            encoding (Encodings, optional): The encoding of the data file.
                Defaults to "utf-8".

        Returns:
            Self: A new instance of `CrossDataResource` with the
                provided metadata.
        """
        return cls(
            **contract.model_dump(),
            format=format,
            encoding=encoding,
        )
