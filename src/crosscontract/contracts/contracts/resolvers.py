from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover
    from .base_contract import BaseContract


@runtime_checkable
class ContractResolver(Protocol):
    def resolve(self, name: str) -> "BaseContract | None":
        """Return the contract with the given name, or None if not found."""
        ...
