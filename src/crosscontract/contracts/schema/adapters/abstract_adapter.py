from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from crosscontract.contracts.schema import TableSchema


class AbstractAdapter(ABC):
    """
    Abstract base class for schema adapters. Adapters are responsible for converting
    a TableSchema into a specific format, such as a Pydantic model or a Pandera
    DataFrame.
    """

    def __init__(self, schema: "TableSchema", *args, **kwargs: Any):
        self.schema = schema

    @abstractmethod
    def convert(self, *args, **kwargs) -> Any:
        """Convert the given TableSchema into the target format."""
        pass

    @classmethod
    @abstractmethod
    def convert_schema(cls, schema: "TableSchema", *args, **kwargs) -> Any:
        """Convenience method to convert a TableSchema without needing to instantiate
        the adapter. Needs to be implemented by each adapter class to force
        documentation of the expected arguments.

        Args:
            schema (TableSchema): The schema to convert.
            *args: Positional arguments passed on to the conversion.
            **kwargs: Keyword arguments passed on to the conversion.

        Returns:
            Any: The schema in the adapter's target format.
        """
        pass
