from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from crosscontract.contracts.schema import TableSchema


class AbstractAdapter(ABC):
    """
    Abstract base class for schema adapters. Adapters are responsible for converting
    a TableSchema into a specific format, such as a Pydantic model, a Pandera DataFrame,
    or SQLAlchemy columns.
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
        documentation of the expected arguments. But can simply call the instance
        method by default."""
        return cls(schema).convert(*args, **kwargs)
