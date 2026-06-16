from typing import Annotated, Any, TypeVar

from pydantic import BeforeValidator

T = TypeVar("T")


def _drop_empty_list(v: Any) -> Any:
    """Collapse an empty list to `None` so an optional field is omitted.

    Frictionless mandates `minItems: 1` on several optional array fields
    (`contributors`, `licenses`, `keywords`). Treating `[]` as "not provided"
    lets `exclude_none` drop the key entirely rather than emit an invalid empty
    array.

    Args:
        v (Any): The raw field value before validation.

    Returns:
        Any: `None` if `v` is an empty list, otherwise `v` unchanged.
    """
    return None if isinstance(v, list) and not v else v


OptionalNonEmptyList = Annotated[list[T] | None, BeforeValidator(_drop_empty_list)]

__all__ = ["OptionalNonEmptyList"]
