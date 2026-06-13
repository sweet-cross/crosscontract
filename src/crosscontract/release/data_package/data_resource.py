"""A `CrossDataResource` is the frictionless compliant representation of a
`CrossContract` together with the description of the data source. The data source is
always a file that is assumed to be distributed within a (zip) folder together with
this descriptor. I.e., the `CrossDataResource` is self-contained. It is the same as
the `CrossContract` but augmented by a description of the data file.

"""

from typing import Any, Literal, Self

from ...contracts import CrossContract
from .models_resource import CrossDataResourceMetaData, FileMetaData

Formats = Literal["csv", "parquet"]
Encodings = Literal["utf-8", "utf-16", "latin-1"]


class CrossDataResource(CrossDataResourceMetaData, FileMetaData):
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

    schema: dict[str, Any]  # from tableschema in CrossContract

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
        meta = contract.model_dump(include=set(CrossDataResourceMetaData.model_fields))
        return cls(
            **meta,
            schema=contract.model_dump()["tableschema"],
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
        descriptor = self.model_dump(mode="json", exclude_none=True)
        return descriptor
